
import asyncio
import uvloop
import operator
import os

from .parameters import Parameters
from .logger import Logger, start_logging, stop_logging
from .utils import adapter
from .config import load_settings
from .database import DatabasePool
from .loader import load_dir

from . import predicates
from . import lifespan
from . import http

class Handler:
	def __init__(self, config_file, endpoints_dir):

		self.settings = None
		self.endpoints_dir = endpoints_dir
		self.db_pool = DatabasePool()
		self.parameters = Parameters(self.db_pool)
		self.builtin_scripts = list()

		async def init():
			Logger.info("Starting up Pavão...")
			self.settings = load_settings(config_file)
			start_logging(self.settings)

			self.load_builtin_endpoints()
			await self.db_pool.setup(self.settings)
			registry = await self.load_external_endpoints()

			if registry is None:
				Logger.warning("No endpoints loaded, aborting...")
				await stop()
				return False

			await self.register_builtin(registry)
			await self.http_handler.init(self.settings, registry)
			Logger.info("Pavão started!")
			return True

		async def stop():
			Logger.info("Stopping Pavão...")
			await self.db_pool.close()
			stop_logging()

		self.lifespan_handler = lifespan.LifespanHandler(init, stop)
		self.http_handler = http.HttpHandler(self.db_pool)
		self.loop = uvloop.new_event_loop()

	#-------------------------------------------------------------------------------

	class EndpointData:
		def __init__(self, specs):
			self.function = adapter(specs['processor'])
			self.package = specs.get('package')
			self.functionality = specs.get('functionality')
			self.public = specs.get('public', False)


	async def load_external_endpoints(self):
		loaded_scripts = load_dir(self.endpoints_dir)
		if len(loaded_scripts) == 0:
			return None

		new_registry = http.Registry()
		routing_destructor = operator.itemgetter('method', 'path')

		async with self.db_pool.connection() as db_connection:

			all_args = {
				'settings': self.settings,
				'db_connection': db_connection,
				'parameters': self.parameters
			}

			for file_path, file_hash, specs_fnc in loaded_scripts:

				try:
					wrapped_fnc = adapter(specs_fnc)
					endpoint_specs = await wrapped_fnc(all_args)

					method, path = routing_destructor(endpoint_specs)
					new_registry.add_endpoint(method, path,
						Handler.EndpointData(endpoint_specs))

				except KeyError as e:
					msg = f"Incomplete spec in '{file_path}': missing field {e}"
					Logger.warning(msg)
					continue

				except Exception as e:
					msg = f"Unable to process specs from file '{file_path}': {e}"
					Logger.warning(msg)
					continue

		return new_registry

	#-------------------------------------------------------------------------------

	def load_builtin_endpoints(self):
		script_path = os.path.dirname(os.path.realpath(__file__))
		builtins_path = os.path.join(script_path, "http", "endpoints")
		self.builtin_scripts = load_dir(builtins_path)


	async def register_builtin(self, registry):
		routing_destructor = operator.itemgetter('method', 'path')

		async with self.db_pool.connection() as db_connection:

			all_args = {
				'settings': self.settings,
				'db_connection': db_connection,
				'parameters': self.parameters
			}

			for file_path, file_hash, specs_fnc in self.builtin_scripts:
				wrapped_fnc = adapter(specs_fnc)
				specs = await wrapped_fnc(all_args)

				method, path = routing_destructor(specs)
				registry.add_endpoint(method, path,
					Handler.EndpointData(specs))

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

