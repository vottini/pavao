
import os
import asyncio
import uvloop
import traceback
import operator

from .exception import PavaoException
from .config import load_settings
from .logger import Logger, start_logging, stop_logging
from .utils import adapter, async_adapter, remove_prefix, WrappedFunction
from .loader import load_component, load_components_dir
from .loader import retrieve_dependees, load_module, load_folder
from .refresher import PathMonitor
from .endpoint import EndpointData
from .registry import Registry
from .scheduler import Scheduler
from .daemon import Daemon
from .broadcasting import Broadcaster
from .supplier import ParameterFactory, ParameterException
from .filter import FilterCollection

from . import predicates
from . import lifespan
from . import http

python_source = lambda x : x.endswith('.py')
non_python_source = lambda x : not python_source(x)

routing_destructor = operator.itemgetter(
	'method',
	'path',
	'processor'
)

base_parameters = {
	'server',
	'request',
	'response',
	'endpoint_specs',
	'path_variables',
	'broadcasting',
	'receive'
}

def create_processing_pipeline(
	pre_filtering,
	filtering,
	processor,
	post_filtering):

	async def full_preprocessing(context):

		try:
			for preprocessor in pre_filtering:
				await preprocessor(context)

			for allower in filtering:
				can_proceed = await allower(context)
				if not can_proceed:
					break

			else:
				await processor(context)

		finally:
			for postprocessor in post_filtering:
				await postprocessor(context)

	return full_preprocessing

#-------------------------------------------------------------------------------

class Server:
	def __init__(self,
		config_file, is_default_file,
		foundation_dir, modules_dir):

		self.loaded_settings = None
		self.modules_dir = os.path.abspath(modules_dir)
		self.monitor = PathMonitor(self.modules_dir,
			self.update_modules)

		self.broadcaster = Broadcaster()
		self.parametering = ParameterFactory(base_parameters)
		self.filtering = FilterCollection()

		self.services = dict()
		self.endpoints = dict()
		self.tasks = dict()

		async def init():
			Logger.info("Starting up Pavão...")
			self.loaded_settings = load_settings(config_file, is_default_file)
			start_logging(self.loaded_settings)

			self.load_builtin_foundation()
			self.load_user_foundation(foundation_dir)

			await self.http_handler.init(self.loaded_settings)
			await self.parametering.init(self.loaded_settings)
			await self.filtering.init(self.loaded_settings,
				self.parametering)

			await self.load_user_modules()
			await self.register_endpoints()
			await self.restart_tasks()

			self.monitor.schedule_execution(self.loop)
			Logger.info("Pavão started!")
			return True

		async def stop():
			Logger.info("Stopping Pavão...")
			self.monitor.stop()

			await self.scheduler.stop()
			await self.daemon.stop()
			await self.parametering.shutdown()

			stop_logging()

		self.lifespan_handler = lifespan.LifespanHandler(init, stop)
		self.http_handler = http.HttpHandler(self, self.broadcaster)

		self.loop = uvloop.new_event_loop()
		self.scheduler = Scheduler(self.loop, self.broadcaster)
		self.daemon = Daemon(self.loop, self.broadcaster)

	#-------------------------------------------------------------------------------

	async def load_modules(self,
		endpoint_destination,
		task_destination,
		service_destination,
		*scripts):

		if len(scripts) == 0:
			return

		destinations = {
			'ENDPOINT': endpoint_destination,
			'SERVICE': service_destination,
			'TASK': task_destination,
		}

		for file_path, (kind, initializer) in scripts:
			context = { 'loaded_settings': self.loaded_settings }

			try:
				context = await self.parametering.prepare_context(initializer, context)
				wrapped_fnc = async_adapter(adapter(initializer))
				specs = await wrapped_fnc(context)
				if specs is None:
					continue

				destination = destinations[kind]
				destination[file_path] = specs

			except KeyError as e:
				msg = f"Incomplete spec in '{file_path}': missing field {e}"
				Logger.warning(msg)
				continue

			except ParameterException as e:
				short_path = os.path.relpath(file_path, self.modules_dir)
				msg = f"'{short_path}' register function: {e}"
				Logger.warning(msg)
				continue

			except Exception as e:
				msg = f"Unable to process specs from file '{file_path}': {e}"
				Logger.error(traceback.format_exc())
				Logger.warning(msg)
				continue

			finally:
				for parameter, value in context.items():
					await self.parametering.destroy(parameter,
						value)

	#-------------------------------------------------------------------------------

	def load_builtin_foundation(self):
		Logger.info("Loading builtin foundation...")
		basepath = os.path.dirname(os.path.realpath(__file__))
		base_foundation_path = os.path.join(basepath, "builtin", "foundation")
		load_folder(base_foundation_path, False)


	def load_user_foundation(self, foundation_dir):
		if foundation_dir is not None:
			Logger.info("Loading user foundation...")
			load_folder(foundation_dir, True)


	async def load_user_modules(self):
		Logger.info(f"Scanning '{self.modules_dir}'")
		script_files = load_components_dir(self.modules_dir, True)

		await self.load_modules(
			self.endpoints,
			self.tasks,
			self.services,
			*script_files)

	#-------------------------------------------------------------------------------

	async def register_endpoints(self):
		all_filters = self.filtering.list_filters()
		enabler_parametering = self.parametering.change_base(
			{'endpoint_specs'}
		)

		filter_list = list()
		for classname, enabler, allower in all_filters:

			try:
				pre_enabler, post_enabler = enabler_parametering.create_wrappers(enabler)
				wrapped_enabler = WrappedFunction(pre_enabler,
					async_adapter(adapter(enabler)),
					post_enabler)

				filter_list.append((wrapped_enabler, allower))

			except ParameterException as e:
				Logger.error(f"Unable to use filter {classname}: {e}")
				Logger.error(traceback.format_exc())
				raise e

		registry = Registry()
		for specs in self.endpoints.values():

			try:
				method, path, processor = routing_destructor(specs)
				unknown_dep = self.parametering.unknown_deps(processor)

				try:
					if unknown_dep is not None:
						msg = f"missing parameter '{unknown_dep}'"
						raise ParameterException(msg)

					wrappers = self.parametering.create_wrappers(processor)
					pre_processor, post_processor = wrappers

					endpoint_processing = WrappedFunction(pre_processor,
						async_adapter(adapter(processor)),
						post_processor)

					filtering = list()
					pre_filtering = list()
					post_filtering = list()

					for wrapped_enabler, allower in filter_list:
						context = { 'endpoint_specs': specs }
						should_enable = await wrapped_enabler(context)

						if should_enable:
							preproc, postproc = self.parametering.create_wrappers(allower)
							filtering.append(async_adapter(adapter(allower)))
							if preproc is not None: pre_filtering.append(preproc)
							if postproc is not None: post_filtering.append(postproc)

					post_filtering = reversed(post_filtering)
					full_processing = create_processing_pipeline(
						pre_filtering, filtering,
						endpoint_processing,
						post_filtering)

					endpoint = EndpointData(full_processing, specs)
					registry.add_endpoint(method, path, endpoint)

				except ParameterException as e:
					Logger.warning(f"'{method} {path}' disabled: {e}")
					continue

			except Exception as e:
				Logger.warning(f"Unable to add endpoint: {e}")
				Logger.error(traceback.format_exc())
				continue

		await self.http_handler.update_registry(registry)

	#-------------------------------------------------------------------------------

	def update_modules(self, creations, deletions, updates):
		to_unload = set(filter(python_source, (*deletions, *updates)))
		to_load = set(filter(python_source, (*updates, *creations)))
		print("!!! update_modules")

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
			self.endpoints,
			self.tasks
		]

		for file_path in to_unload:
			if file_path in self.services:
				self.daemon.stop_module(file_path)

				self.services.pop(file_path)
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
				if (specifier := load_component(file_path, self.modules_dir, True)) is not None:
					collected.append((file_path, specifier))

			if len(collected) > 0:
				await self.load_modules(
					self.endpoints,
					self.tasks,
					self.services,
					*collected)

		asyncio.run_coroutine_threadsafe(process_loading(), self.loop)
		asyncio.run_coroutine_threadsafe(self.register_endpoints(), self.loop)
		asyncio.run_coroutine_threadsafe(self.restart_tasks(), self.loop)


	def parse_tasks(self, modules, manager):
		parsed_tasks = list()

		for file_path, spec in modules.items():
			task_parametering = self.parametering.change_base(
				manager.get_base_context())

			try:
				task_data = manager.ctor(file_path, spec)
				unknown_dep = task_parametering.unknown_deps(
					task_data.processor)

				try:
					if unknown_dep is not None:
						msg = f"missing parameter '{unknown_dep}'"
						raise ParameterException(msg)

					wrappers = task_parametering.create_wrappers(
						task_data.processor)

				except ParameterException as e:
					short_path = os.path.relpath(file_path, self.modules_dir)
					Logger.warning(f"'{short_path}' disabled: {e}")
					continue

				pre_processor, post_processor = wrappers
				full_processing = WrappedFunction(pre_processor,
					adapter(task_data.processor, False),
					post_processor)

				parsed_tasks.append(task_data)

			except KeyError as e:
				msg = f"Incomplete spec in '{file_path}': missing field {e}"
				Logger.warning(msg)
				continue

			except Exception as e:
				short_path = os.path.relpath(file_path, self.modules_dir)
				Logger.warning(f"Problem with task in file '{short_path}': {e}")
				continue

		return parsed_tasks


	async def restart_tasks(self):
		internal_db = await self.parametering.produce('internal_db')

		await self.scheduler.set_tasks(
			self.parse_tasks(self.tasks, self.scheduler),
			internal_db)

		await self.daemon.set_tasks(
			self.parse_tasks(self.services, self.daemon),
			internal_db)

	#-------------------------------------------------------------------------------

	def deactivate(self):
		self.http_handler.deactivate()

		async def announcing():
			Logger.info("Closing broadcast open sinks...")
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

