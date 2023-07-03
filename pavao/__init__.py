
import asyncio
import inspect
import uvloop
import operator
import os

from . import predicates
from .utils import *
from .exception import *
from .config import *
from .logger import *
from .database import *
from .lifespan import *
from .http import *
from .loader import *
from .json import *

class Handler:
	def __init__(self, config_file, endpoints_dir):

		self.settings = None
		self.endpoints_dir = endpoints_dir
		self.db_pool = DatabasePool()
		self.builtin_scripts = list()

		async def init():
			Logger.info("Starting up Pavão...")
			self.settings = loadSettings(config_file)
			startLogging(self.settings)

			self.load_builtin_endpoints()
			await self.db_pool.setup(self.settings)
			registry = await self.load_external_endpoints()

			if registry is None:
				Logger.warning("No endpoints loaded, aborting...")
				await stop()
				return False

			await self.register_builtin(registry)
			await self.httpHandler.init(registry)
			Logger.info("Pavão started!")
			return True

		async def stop():
			Logger.info("Stopping Pavão...")
			await self.db_pool.close()
			stopLogging()

		self.lifespanHandler = lifespan.LifespanHandler(init, stop)
		self.httpHandler = http.HttpHandler(self.db_pool)
		self.loop = uvloop.new_event_loop()

	#-------------------------------------------------------------------------------

	class Endpoint:
		def __init__(self, specs):
			self.function = specs['processor']
			self.public = specs.get('public', False)
			self.functionality = specs.get('functionality')
			self.init = specs.get('init')

		async def setup(self, settings, db_pool):
			if self.init is not None:
				async with db_pool.connection() as db_conn:
					await self.init(settings, db_conn)


	async def load_external_endpoints(self):
		loaded_scripts = load_dir(self.endpoints_dir)
		if len(loaded_scripts) == 0:
			return None

		new_registry = http.Registry()
		routing_destructor = operator.itemgetter('method', 'path')
		for file_path, file_hash, specs_fnc in loaded_scripts:

			try:
				specs = specs_fnc()
				method_and_path = routing_destructor(specs)
				processor = Handler.Endpoint(specs)

				await processor.setup(self.settings, self.db_pool)
				new_registry.add_endpoint(*method_and_path,
					processor)

			except KeyError as e:
				Logger.warning(f"Incomplete spec in '{file_path}': missing field {e}")
				continue

			except Exception as e:
				Logger.warning(f"Unable to process specs from file '{file_path}': {e}")
				continue

		return new_registry

	#-------------------------------------------------------------------------------

	def load_builtin_endpoints(self):
		script_path = os.path.dirname(os.path.realpath(__file__))
		builtins_path = os.path.join(script_path, "http", "builtin")
		self.builtin_scripts = load_dir(builtins_path)


	async def register_builtin(self, registry):
		routing_destructor = operator.itemgetter('method', 'path')
		for file_path, file_hash, specs_fnc in self.builtin_scripts:

			specs = specs_fnc()
			method_and_path = routing_destructor(specs)
			processor = Handler.Endpoint(specs)

			await processor.setup(self.settings, self.db_pool)
			registry.add_endpoint(*method_and_path,
				processor)

	#-------------------------------------------------------------------------------

	def get_app(self):
	
		handlers = (
			('http', self.httpHandler),
			('lifespan', self.lifespanHandler)
		)
	
		async def app(scope, receive, send):
			for handler_type, handler in handlers:
				if scope['type'] == handler_type:
					await handler.handle(scope, receive, send)
					break

		return app

