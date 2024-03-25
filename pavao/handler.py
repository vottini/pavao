
import os
import asyncio
import uvloop
import operator
import traceback

from croniter import croniter
from datetime import datetime, timedelta

from .utils import adapter
from .config import load_settings, PersistedSettings
from .logger import Logger, start_logging, stop_logging
from .database import DatabasePool
from .loader import load_file, load_dir, retrieve_dependees, load_module
from .refresher import PathMonitor

from . import predicates
from . import lifespan
from . import http

python_source = lambda x : x.endswith('.py')
non_python_source = lambda x : not python_source(x)
routing_destructor = operator.itemgetter('method', 'path')

#-------------------------------------------------------------------------------

class EndpointData:
	def __init__(self, specs):
		self.function = adapter(specs['processor'])
		self.package = specs.get('package')
		self.functionality = specs.get('functionality')
		self.public = specs.get('public', False)


class TaskData:
	def __init__(self, specs, start_time):
		self.package = specs.get('package')
		self.functionality = specs.get('functionality')
		self.function = adapter(specs['processor'])
		self.schedule = specs['schedule']
		self.execution = None

		self.last_execution = None
		self.iterator = croniter(self.schedule, start_time)
		self.next_execution = self.iterator.get_next(datetime)
		self.last_result = None


	def register_execution(self, task):
		self.execution = None

		try:
			result = task.result()
			self.last_result = (True, result)

		except asyncio.CancelledError as e:
			self.last_result = (False, "Cancelled during execution")

		except Exception as e:
			self.last_result = (False, str(e))


	def create_future(self, args):
		async def async_task():
			result = await self.function(args)
			return result

		return async_task


	def cancel_if_executing(self):
		if self.execution is not None:
			self.execution.cancel()
			self.execution = None


	def lateness(self):
		now = datetime.now()
		elapsed = now - self.next_execution
		return max(elapsed, timedelta())


	def step_schedule(self):
		self.next_execution = self.iterator.get_next(datetime)


	def execute(self, handler):
		self.cancel_if_executing()

		all_args = {
			'db_pool': handler.db_pool,
			'handler': handler
		}

		self.last_execution = datetime.now()
		task_future = self.create_future(all_args)
		task = handler.loop.create_task(task_future())
		task.add_done_callback(self.register_execution)
		self.execution = task

#-------------------------------------------------------------------------------

async def wait_whole_minute():
	now = datetime.now()
	wait = (59-now.second) + (1000000-now.microsecond)/1e6
	await asyncio.sleep(wait)

	then = datetime.now()
	waited = then - now
	if waited > timedelta(minutes=2):
		await wait_whole_minute()


class Handler:
	def __init__(self, config_file, endpoints_dir):

		self.settings = None
		self.endpoints_dir = os.path.abspath(endpoints_dir)
		self.monitor = PathMonitor(self.endpoints_dir, self.update_endpoints)
		self.db_pool = DatabasePool()

		self.builtin_endpoints = dict()
		self.external_endpoints = dict()
		self.builtin_tasks = dict()
		self.external_tasks = dict()

		async def init():
			Logger.info("Starting up Pavão...")
			self.settings = load_settings(config_file)
			start_logging(self.settings)

			await self.db_pool.setup(self.settings)
			await self.http_handler.init(self.settings)
			await self.load_builtin_endpoints()

			script_files = load_dir(self.endpoints_dir)
			await self.load_endpoints(
				self.external_endpoints,
				self.external_tasks,
				*script_files)

			await self.register_endpoints()
			self.schedule_tasks()

			self.monitor.schedule_execution(self.loop)
			Logger.info("Pavão started!")
			return True

		async def stop():
			Logger.info("Stopping Pavão...")

			self.monitor.stop()
			if self.scheduler is not None:
				self.scheduler.cancel()

			await self.db_pool.close()
			stop_logging()

		self.scheduler = None
		self.loaded_tasks = list()

		self.persisted = PersistedSettings(self.db_pool)
		self.lifespan_handler = lifespan.LifespanHandler(init, stop)
		self.http_handler = http.HttpHandler(self.db_pool)
		self.loop = uvloop.new_event_loop()

	#-------------------------------------------------------------------------------

	async def register_endpoints(self):
		registry = http.Registry()

		await self.add_endpoints(self.builtin_endpoints, registry)
		await self.add_endpoints(self.external_endpoints, registry)
		await self.http_handler.update_registry(registry)


	def schedule_tasks(self):
		if self.scheduler is not None:
			self.scheduler.cancel()
			self.scheduler = None

		tasks = list()
		start = datetime.now()
		for source in [ self.builtin_tasks, self.external_tasks ]:
			for file_path, spec in source.items():

				try:
					taskData = TaskData(spec, start)
					tasks.append(taskData)

				except KeyError as e:
					msg = f"Incomplete spec in '{file_path}': missing field {e}"
					Logger.warning(msg)
					continue

		self.loaded_tasks = tasks
		self.scheduler = self.loop.create_task(self.execute_tasks())

	#------------------------------------------------------------

	async def execute_tasks(self):
		skippable_lateness = timedelta(
			minutes=1, seconds=30)

		while len(self.loaded_tasks) > 0:
			await wait_whole_minute()
			now = datetime.now()

			for task in self.loaded_tasks:
				while task.lateness() > skippable_lateness:
					task.step_schedule()

				if task.next_execution <= now:
					task.execute(self)
					task.step_schedule()

	#-------------------------------------------------------------------------------

	def update_endpoints(self, creations, deletions, updates):
		to_unload = set(filter(python_source, (*deletions, *updates)))
		to_load = set(filter(python_source, (*updates, *creations)))

		#print("RUNNING update_endpoints")

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

		for file_path in to_unload:
			if file_path in self.external_endpoints:
				self.external_endpoints.pop(file_path)
				Logger.info(f"Unloaded endpoint from {file_path}")
				continue

			if file_path in self.external_tasks:
				self.external_tasks.pop(file_path)
				Logger.info(f"Unloaded task from {file_path}")
				continue

		async def process_loading():
			for dependency in updated_dependencies:
				load_module(dependency)

			collected = list()
			for file_path in to_load:
				if (specifier := load_file(file_path)) is not None:
					collected.append((file_path, specifier))

			if len(collected) > 0:
				await self.load_endpoints(
					self.external_endpoints,
					self.external_tasks,
					*collected)

		asyncio.run_coroutine_threadsafe(process_loading(), self.loop)
		asyncio.run_coroutine_threadsafe(self.register_endpoints(), self.loop)
		self.schedule_tasks()

	#-------------------------------------------------------------------------------

	async def load_endpoints(self,
		endpoint_destination,
		task_destination,
		*scripts):

		if len(scripts) == 0:
			return

		destinations = {
			'ENDPOINT': endpoint_destination,
			'TASK': task_destination
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


	async def add_endpoints(self, endpoint_container, registry):
		for file_path, endpoint in endpoint_container.items():
			method, path = routing_destructor(endpoint)
			registry.add_endpoint(method, path,
				EndpointData(endpoint))

	#-------------------------------------------------------------------------------

	async def load_builtin_endpoints(self):
		script_path = os.path.dirname(os.path.realpath(__file__))
		builtins_path = os.path.join(script_path, "http", "endpoints")
		script_files = load_dir(builtins_path)

		await self.load_endpoints(
			self.builtin_endpoints,
			self.builtin_tasks,
			*script_files)

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

