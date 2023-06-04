
import asyncio
import uvloop

from .exception import *
from .config import *
from .logger import *
from .database import *
from .lifespan import *
from .http import *
from .loader import *

#from starlette.applications import Router
#from starlette.responses import JSONResponse, HTMLResponse
#from starlette.routing import Route

#async def homepage(request):
#	response = HTMLResponse('<html><body><h1>Hello World!</h1></body></html>')
#	return response
#
#async def login(request):
#	async with database_connection() as conn:
#		response = JSONResponse({'hello': 'world'})
#		response.set_cookie("refresh-token", "lalala", path="/token-refresh", httponly=True, samesite="strict")
#		return response

#routes = [
#	Route('/', homepage),
#	Route('/login', login),
#]

#setup_database(loop, "localhost", 5432, "talaria", "talaria_admin")
#app = Router(routes=routes)

class Handler:
	def __init__(self):
		self.loop = uvloop.new_event_loop()
		self.httpHandler = http.HttpHandler()
		self.lifespanHandler = lifespan.LifespanHandler(
			lambda : self.init(),
			lambda : self.close()
		)


	def load_endpoints(self):
		registry = http.Registry()
		#load_endpoints(path, router)
		self.httpHandler.set_registry(registry)
		pass
	
	#-------------------------------------------------------------------------------
	
	def init(self):
		print("Iniciando...")
		self.load_endpoints()
	
	
	def close(self):
		print("Encerrando...")
		
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

