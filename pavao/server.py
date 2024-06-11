
import os
import asyncio
import uvloop
import traceback

from .utils import adapter, remove_prefix
from .config import load_settings, PersistedSettings
from .logger import Logger, start_logging, stop_logging
from .database import DatabasePool
from .loader import load_file, load_dir, retrieve_dependees, load_module
from .refresher import PathMonitor
from .registry import Registry
from .scheduler import Scheduler
from .broadcasting import Broadcaster
from .authorizer import Authorizer

from . import predicates
from . import lifespan
from . import http

python_source = lambda x : x.endswith('.py')
non_python_source = lambda x : not python_source(x)

#-------------------------------------------------------------------------------

class Server:
	def __init__(self, config_file, modules_dir):

		self.settings = None
		self.modules_dir = os.path.abspath(modules_dir)
		self.monitor = PathMonitor(self.modules_dir, self.update_modules)
		self.db_pool = DatabasePool()

		self.authorizer = Authorizer()
		self.broadcaster = Broadcaster()
		self.registry = Registry()

		self.builtin_services = dict()
		self.builtin_endpoints = dict()
		self.builtin_tasks = dict()

		self.external_services = dict()
		self.external_endpoints = dict()
		self.external_tasks = dict()

		async def init():
			Logger.info("Starting up Pavão...")
			self.settings = load_settings(config_file)
			start_logging(self.settings)

			await self.db_pool.setup(self.settings)
			await self.http_handler.init(self.settings)
			await self.load_builtin_modules()

			Logger.info(f"Loading scripts at '{self.modules_dir}'")
			script_files = load_dir(self.modules_dir, True)

			await self.load_modules(
				self.external_endpoints,
				self.external_tasks,
				self.external_services,
				*script_files)

			await self.register_endpoints()
			await self.start_services()

			self.scheduler.parse_tasks({
				**self.builtin_tasks,
				**self.external_tasks
			})

			self.monitor.schedule_execution(self.loop)
			Logger.info("Pavão started!")
			return True

		async def stop():
			Logger.info("Stopping Pavão...")
			self.monitor.stop()
			self.scheduler.stop()
			await self.db_pool.close()
			stop_logging()

		self.loop = uvloop.new_event_loop()
		self.persisted = PersistedSettings(self.db_pool)
		self.lifespan_handler = lifespan.LifespanHandler(init, stop)
		self.http_handler = http.HttpHandler(self)

		self.scheduler = Scheduler(self.loop, self)

	#-------------------------------------------------------------------------------

	async def load_modules(self,
		endpoint_destination,
		task_destination,
		service_destination,
		*scripts):

		if len(scripts) == 0:
			return

		destinations = {
			'SERVICE': service_destination,
			'ENDPOINT': endpoint_destination,
			'TASK': task_destination,
		}

		async with self.db_pool.connection() as db_connection:

			all_args = {
				'loaded_settings': self.settings,
				'persisted_settings': self.persisted,
				'db_connection': db_connection
			}

			for file_path, specifier in scripts:
				kind, method = specifier

				try:
					wrapped_fnc = adapter(method)
					specs = await wrapped_fnc(all_args)
					destinations[kind][file_path] = specs

				except KeyError as e:
					msg = f"Incomplete spec in '{file_path}': missing field {e}"
					Logger.warning(msg)
					continue

				except Exception as e:
					msg = f"Unable to process specs from file '{file_path}': {e}"
					Logger.warning(msg)
					continue


	async def load_builtin_modules(self):
		Logger.info("Loading builtin modules...")

		script_path = os.path.dirname(os.path.realpath(__file__))
		builtins_path = os.path.join(script_path, "http", "endpoints")
		script_files = load_dir(builtins_path, True)

		await self.load_modules(
			self.builtin_endpoints,
			self.builtin_tasks,
			self.builtin_services,
			*script_files)

	#-------------------------------------------------------------------------------

	async def register_endpoints(self):

		all_specs = [
			*self.builtin_endpoints.values(),
			*self.external_endpoints.values()
		]

		registry = Registry()
		for spec in all_specs:
			registry.add_endpoint(spec)

		await self.http_handler.update_registry(registry)


	async def start_services(self):
		pass

	#-------------------------------------------------------------------------------

	def update_modules(self, creations, deletions, updates):
		to_unload = set(filter(python_source, (*deletions, *updates)))
		to_load = set(filter(python_source, (*updates, *creations)))

		#print("RUNNING update_modules")

		updated_dependencies = set()
		for script in filter(python_source, updates):
			if len(dependees := retrieve_dependees(script)) > 0:
				updated_dependencies.add(script)
				to_load.remove(script)
				to_unload |= dependees
				to_load |= dependees

		for file in filter(non_python_source, (*deletions, *updates)):
			dependees = set(retrieve_dependees(file))
			to_unload |= dependees
			to_load |= dependees

		external_origins = [
			self.external_services,
			self.external_endpoints,
			self.external_tasks
		]

		for file_path in to_unload:
			for origin in external_origins:
				if file_path in origin:
					origin.pop(file_path)
					specific_path = remove_prefix(file_path, self.modules_dir)
					Logger.info(f"Unloaded endpoint from {specific_path}")
					continue

		async def process_loading():
			for dependency in updated_dependencies:
				load_module(dependency)

			collected = list()
			for file_path in to_load:
				if (specifier := load_file(file_path, self.modules_dir, True)) is not None:
					collected.append((file_path, specifier))

			if len(collected) > 0:
				await self.load_modules(
					self.external_endpoints,
					self.external_tasks,
					self.external_services,
					*collected)

		asyncio.run_coroutine_threadsafe(process_loading(), self.loop)
		asyncio.run_coroutine_threadsafe(self.register_endpoints(), self.loop)

		self.scheduler.parse_tasks({
			**self.builtin_tasks,
			**self.external_tasks
		})

	#-------------------------------------------------------------------------------

	def terminate_connections(self):
		Logger.info("Closing connections...")

		async def announcing():
			await self.broadcaster.announce_shutdown()

		self.loop.create_task(announcing())

	#-------------------------------------------------------------------------------

	def get_app(self):

		handlers = (
			('http', self.http_handler),
			('lifespan', self.lifespan_handler)
		)

		async def app(scope, receive, send):
			for handler_type, handler in handlers:
				if scope['type'] == handler_type:
					await handler.handle(scope, receive, send)
					break

		return app

