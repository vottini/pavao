
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
from .daemon import Daemon
from .broadcasting import Broadcaster
from .authorizer import Authorizer

from . import predicates
from . import lifespan
from . import http

python_source = lambda x : x.endswith('.py')
non_python_source = lambda x : not python_source(x)

#-------------------------------------------------------------------------------

class Server:
	def __init__(self, config_file, is_default_file, modules_dir):

		self.loaded_settings = None
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
			self.loaded_settings = load_settings(config_file, is_default_file)
			start_logging(self.loaded_settings)

			await self.db_pool.setup(self.loaded_settings)
			await self.http_handler.init(self.loaded_settings)
			await self.load_builtin_modules()

			Logger.info(f"Scanning '{self.modules_dir}'")
			script_files = load_dir(self.modules_dir, True)

			await self.load_modules(
				self.external_endpoints,
				self.external_tasks,
				self.external_services,
				*script_files)

			self.scheduler.parse_tasks({**self.builtin_tasks, **self.external_tasks})
			self.daemon.parse_tasks({**self.builtin_services, **self.external_services})
			await self.register_endpoints()

			self.monitor.schedule_execution(self.loop)
			Logger.info("Pavão started!")
			return True

		async def stop():
			Logger.info("Stopping Pavão...")
			self.monitor.stop()
			self.scheduler.stop()
			await self.daemon.stop()
			await self.db_pool.close()
			stop_logging()

		self.loop = uvloop.new_event_loop()
		self.persisted_settings = PersistedSettings(self.db_pool)
		self.lifespan_handler = lifespan.LifespanHandler(init, stop)
		self.http_handler = http.HttpHandler(self)

		self.scheduler = Scheduler(self.loop, self)
		self.daemon = Daemon(self.loop, self)

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
				'loaded_settings': self.loaded_settings,
				'persisted_settings': self.persisted_settings,
				'db_connection': db_connection
			}

			for file_path, specifier in scripts:
				kind, initializer = specifier

				try:
					wrapped_fnc = adapter(initializer)
					specs = await wrapped_fnc(all_args)
					if specs is None: continue
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
		builtins_path = os.path.join(script_path, "builtin")
		script_files = load_dir(builtins_path, False)

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
			try: registry.add_endpoint(spec)
			except Exception as e:
				msg = f"Unable to add endpoint: {e}"
				Logger.warning(msg)
				continue

		await self.http_handler.update_registry(registry)

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

		endpoints_and_tasks = [
			self.external_endpoints,
			self.external_tasks
		]

		for file_path in to_unload:
			if file_path in self.external_services:
				self.daemon.stop_module(file_path)

				self.external_services.pop(file_path)
				specific_path = remove_prefix(file_path, self.modules_dir)
				Logger.info(f"Unloaded service from {specific_path}")
				continue

			for origin in endpoints_and_tasks:
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
		asyncio.run_coroutine_threadsafe(self.restart_tasks(), self.loop)


	async def restart_tasks(self):
		self.scheduler.stop()
		self.scheduler.parse_tasks({
			**self.builtin_tasks,
			**self.external_tasks}
		)

		await self.daemon.stop()
		self.daemon.parse_tasks({
			**self.builtin_services,
			**self.external_services}
		)

	#-------------------------------------------------------------------------------

	def deactivate(self):
		self.http_handler.deactivate()
		Logger.info("Closing connections...")
		async def announcing(): await self.broadcaster.announce_shutdown()
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

