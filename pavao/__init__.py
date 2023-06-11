
import asyncio
import inspect
import uvloop
import operator

from .exception import *
from .config import *
from .logger import *
from .database import *
from .lifespan import *
from .http import *
from .loader import *

class Handler:
	def __init__(self, config_file, endpoints_dir):

		self.settings = None
		self.endpoints_dir = endpoints_dir
		self.db_pool = DatabasePool()
		self.loaded_scripts = list()

		async def init():
			Logger.info("Starting up Pavão...")
			self.settings = loadSettings(config_file)
			startLogging(self.settings)

			self.load_endpoints()
			if len(self.loaded_scripts) == 0:
				Logger.warning("No endpoints loaded, aborting...")
				stopLogging()
				return False

			await self.db_pool.setup(self.settings)
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


	def load_endpoints(self):
		routing_destructor = operator.itemgetter('method', 'path')
		loaded_scripts = load_dir(self.endpoints_dir)

		new_registry = http.Registry()
		for file_path, file_hash, specs_fnc in loaded_scripts:

			try:
				specs = specs_fnc()
				method_and_path = routing_destructor(specs)
				processor = Handler.Endpoint(specs)

				new_registry.add_endpoint(
					*method_and_path,
					processor)

			except KeyError as e:
				Logger.warning(f"Incomplete spec in '{file_path}': missing field {e}")
				continue

			except Exception as e:
				Logger.warning(f"Unable to process specs from file '{file_path}': {e}")
				continue

		self.loaded_scripts = loaded_scripts
		self.httpHandler.update_registry(new_registry)

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

