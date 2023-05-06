
import asyncio
import uvloop

from .config import *
from .logger import *
from .token import *
from .database import *

from starlette.applications import Router
from starlette.responses import JSONResponse, HTMLResponse
from starlette.routing import Route

async def homepage(request):
	response = HTMLResponse('<html><body><h1>Hello World!</h1></body></html>')
	return response

async def login(request):
	async with database_connection() as conn:
		response = JSONResponse({'hello': 'world'})
		response.set_cookie("refresh-token", "lalala", path="/token-refresh", httponly=True, samesite="strict")
		return response

routes = [
	Route('/', homepage),
	Route('/login', login),
]

loop = uvloop.new_event_loop()
setup_database(loop, "localhost", 5432, "talaria", "talaria_admin")
app = Router(routes=routes)

