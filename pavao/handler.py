
import os
import asyncio
import uvloop
import operator
import traceback

from .utils import adapter
from .config import load_settings, PersistedSettings
from .logger import Logger, start_logging, stop_logging
from .database import DatabasePool
from .loader import load_file, load_dir
from .refresher import PathMonitor

from . import predicates
from . import lifespan
from . import http

python_source = lambda x : x.endswith('.py')
routing_destructor = operator.itemgetter('method', 'path')

#-------------------------------------------------------------------------------

def print_modifications(creations, deletions, updates):
	if len(deletions) > 0: print(f"Files DELETED: {deletions}")
	if len(creations) > 0: print(f"Files CREATED: {creations}")
	if len(updates) > 0: print(f"Files UPDATED: {updates}")

class Handler:
	def __init__(self, config_file, endpoints_dir):

		self.settings = None
		self.endpoints_dir = endpoints_dir
		self.monitor = PathMonitor(endpoints_dir, self.update_endpoints)
		self.db_pool = DatabasePool()
		self.persisted = PersistedSettings(self.db_pool)
		self.builtin_endpoints = list()
		self.endpoint_scripts = list()
		self.endpoint_specs = dict()

		async def init():
			Logger.info("Starting up Pavão...")
			self.settings = load_settings(config_file)
			start_logging(self.settings)

			await self.db_pool.setup(self.settings)
			await self.http_handler.init(self.settings)
			await self.load_builtin_endpoints()

			self.endpoint_scripts = load_dir(self.endpoints_dir)
			await self.load_external_endpoints(*self.endpoint_scripts)
			await self.register_endpoints()

			self.monitor.schedule_execution(self.loop)
			Logger.info("Pavão started!")
			return True

		async def stop():
			Logger.info("Stopping Pavão...")
			await self.db_pool.close()
			self.monitor.stop()
			stop_logging()

		self.lifespan_handler = lifespan.LifespanHandler(init, stop)
		self.http_handler = http.HttpHandler(self.db_pool)
		self.loop = uvloop.new_event_loop()

	#-------------------------------------------------------------------------------

	async def register_endpoints(self):
		registry = http.Registry()
		await self.register_builtin_endpoints(registry)
		await self.register_external_endpoints(registry)
		await self.http_handler.update_registry(registry)


	def update_endpoints(self, creations, deletions, updates):
		to_unload = filter(python_source, (*deletions, *updates))
		to_load = filter(python_source, (*updates, *creations))

		for file_path in to_unload:
			method_and_path = self.endpoint_specs.get(file_path)
			if method_and_path is None:
				continue

			Logger.info(f"Unloaded endpoint from {file_path}")
			self.endpoint_specs.pop(file_path)

		async def load_endpoints():
			collected = list()

			for file_path in to_load:
				if (specifier := load_file(file_path)) is not None:
					collected.append((file_path, specifier))

			if len(collected) > 0:
				await self.load_external_endpoints(*collected)

		asyncio.run_coroutine_threadsafe(load_endpoints(), self.loop)
		asyncio.run_coroutine_threadsafe(self.register_endpoints(), self.loop)

	#-------------------------------------------------------------------------------

	class EndpointData:
		def __init__(self, specs):
			self.function = adapter(specs['processor'])
			self.package = specs.get('package')
			self.functionality = specs.get('functionality')
			self.public = specs.get('public', False)


	async def load_external_endpoints(self, *scripts):
		if len(scripts) == 0:
			return

		async with self.db_pool.connection() as db_connection:

			all_args = {
				'loaded_settings': self.settings,
				'persisted_settings': self.persisted,
				'db_connection': db_connection
			}

			for file_path, specifier in scripts:

				try:
					wrapped_fnc = adapter(specifier)
					specs = await wrapped_fnc(all_args)
					self.endpoint_specs[file_path] = specs

				except KeyError as e:
					msg = f"Incomplete spec in '{file_path}': missing field {e}"
					Logger.warning(msg)
					continue

				except Exception as e:
					msg = f"Unable to process specs from file '{file_path}': {e}"
					Logger.warning(msg)
					continue


	async def register_external_endpoints(self, registry):
		for file_path, endpoint in self.endpoint_specs.items():
			method, path = routing_destructor(endpoint)
			registry.add_endpoint(method, path,
				Handler.EndpointData(endpoint))

	#-------------------------------------------------------------------------------

	async def load_builtin_endpoints(self):
		script_path = os.path.dirname(os.path.realpath(__file__))
		builtins_path = os.path.join(script_path, "http", "endpoints")
		builtin_scripts = load_dir(builtins_path)

		async with self.db_pool.connection() as db_connection:

			all_args = {
				'loaded_settings': self.settings,
				'persisted_settings': self.persisted,
				'db_connection': db_connection
			}

			for file_path, specifier in builtin_scripts:
				wrapped_fnc = adapter(specifier)
				specs = await wrapped_fnc(all_args)
				self.builtin_endpoints.append(specs)


	async def register_builtin_endpoints(self, registry):
		for endpoint in self.builtin_endpoints:
			method, path = routing_destructor(endpoint)
			registry.add_endpoint(method, path,
				Handler.EndpointData(endpoint))

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

