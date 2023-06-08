
import asyncio
import inspect

async def _secure_call(fnc):
	if inspect.iscoroutinefunction(fnc): return await fnc()
	else: return fnc()

from ..logger import Logger
from .request import Request
from .response import Response, emit
from .registry import Registry
from .token import *

class HttpHandler:
	def __init__(self):
		self.registry = Registry()


	def set_registry(self, registry):
		self.registry = registry


	async def handle(self, scope, receive, send):

		try:
			request = Request(scope)
			response = Response(send)
			found_endpoint = self.registry.find_endpoint(
				request.method,
				request.path)

			if None == found_endpoint:
				response.set_status(404)
				await emit(response)
				return

			handler, path_variables = found_endpoint
			handler_params = handler.__code__.co_varnames

			all_args = {
				'request': request,
				'path_variables': path_variables,
				'response': response
			}

			selected_args = list()
			for param_name in handler_params:
				selected_args.append(all_args[param_name])

			await handler(*selected_args)
			await emit(response)

		except Exception as e:
			Logger.error(f"Error processing request: {e}")
			response.set_status(500)
			await emit(response)

