
import asyncio
import inspect
import traceback

from ..logger import Logger
from .request import Request
from .response import Response, emit
from .authorizer import Authorizer
from .registry import Registry


class HttpHandler:
	def __init__(self, db_pool):
		self.db_pool = db_pool
		self.authorizer = Authorizer()
		self.registry = Registry()

		self.arguments = [
			'request',
			'path_variables',
			'db_connection',
			'auth_data',
			'response',
			'receive'
		]

	def get_arguments(self):
		return ['handler'] + self.arguments

	def set_registry(self, registry):
		self.registry = registry


	async def init(self, registry):
		self.set_registry(registry)
		async with self.db_pool.connection() as db_connection:
			await self.authorizer.setup(db_connection)


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

			endpoint, path_variables = found_endpoint
			has_access, auth_data = await self.authorizer.validate_access(
				request, endpoint)

			if not has_access:
				response.set_status(403)
				await emit(response)
				return

			handler = endpoint.function
			async with self.db_pool.connection() as db_connection:
				all_args = {'handler': self}

				for arg in self.arguments:
					current_value = locals()[arg]
					all_args[arg] = current_value

				await handler(all_args)
				await emit(response)

		except Exception as e:
			Logger.error(f"Error processing request: {e}")
			print(traceback.format_exc())

			response.set_status(500)
			await emit(response)

