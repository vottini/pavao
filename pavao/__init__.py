
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

			Logger.info("Pavão started!")
			return True

		async def stop():
			Logger.info("Stopping Pavão...")
			stopLogging()

		self.lifespanHandler = lifespan.LifespanHandler(init, stop)
		self.httpHandler = http.HttpHandler()
		self.loop = uvloop.new_event_loop()

	#-------------------------------------------------------------------------------

	def load_endpoints(self):
		loaded_scripts = load_dir(self.endpoints_dir)
		new_registry = http.Registry()

		spec_destructer = operator.itemgetter('method', 'path', 'callback')
		for file_path, file_hash, specs_fnc in loaded_scripts:

			try:
				specs = specs_fnc()
				destructured_specs = spec_destructer(specs)
				new_registry.add_endpoint(*destructured_specs)

			except Exception as e:
				Logger.warn(f"Unable to process specs from file '{file_path}': {e}")
				continue

		self.loaded_scripts = loaded_scripts
		self.httpHandler.set_registry(new_registry)

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

