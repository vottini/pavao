
import asyncio
import inspect

from ..logger import Logger
from .request import Request
from .response import Response, emit
from .authorizer import Authorizer
from .registry import Registry

class HttpHandler:
	def __init__(self, db_manager):
		self.db_manager = db_manager
		self.authorizer = Authorizer()
		self.registry = Registry()


	def update_registry(self, registry):
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

			db_connection = None # self.db_manager.get_conn()
			endpoint, path_variables = found_endpoint
			has_access = await self.authorizer.validate_access(
				request, endpoint, db_connection)

			if not has_access:
				response.set_status(403)
				await emit(response)
				return

			handler = endpoint.function
			handler_params = handler.__code__.co_varnames

			all_args = {
				'request': request,
				'path_variables': path_variables,
				'db_connection': db_connection,
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

