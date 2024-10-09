
import asyncio
import inspect
import traceback

from ..logger import Logger
from ..registry import Registry
from ..authorizer import AuthError

from .request import Request
from .response import Response, emit

_http_schema = {
	"CORS": {
		"origins": [str],
		"headers": [str]
	}
}

_enlist_value = lambda value : value if isinstance(value, list) else [value]
_all_methods = ["GET", "POST", "PUT", "PATCH", "DELETE"]

# https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Access-Control-Allow-Origin
# https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Access-Control-Allow-Headers
# https://developer.mozilla.org/en-US/docs/Glossary/CORS-safelisted_request_header

_cors_req_methods = 'access-control-request-method'
_cors_req_headers = 'access-control-request-headers'

_cors_allow_methods = 'access-control-allow-methods'
_cors_allow_credentials = 'access-control-allow-credentials'
_cors_allow_origin = 'access-control-allow-origin'
_cors_allow_headers = 'access-control-allow-headers'

class HttpHandler:
	def __init__(self, server):
		self.server = server
		self.active = True

		self.db_pool = server.db_pool
		self.authorizer = server.authorizer
		self.registry = Registry()

		self.cors_origins = list()
		self.cors_headers = set([
			'accept',
			'accept-language',
			'content-language',
			'content-type',
			'authorization',
		])

		self.arguments = [
			'request',
			'path_variables',
			'db_connection',
			'broadcasting',
			'auth_data',
			'response',
			'receive'
		]


	def get_arguments(self):
		return ['server'] + self.arguments

	def deactivate(self):
		self.active = False

	#------------------------------------------------------------

	async def init(self, settings):
		http_settings = settings.get_setting("pavao.http", _http_schema)

		if http_settings is not None:
			cors_settings = http_settings.get('CORS', dict())
			self.cors_headers.update(cors_settings.get('headers', list()))
			self.cors_origins = cors_settings.get('origins', list())


	async def update_registry(self, registry):
		self.registry = registry
		funcs = set()

		for endpoint in registry.list_endpoints():
			if endpoint.functionality is None: continue
			entry = (endpoint.package, endpoint.functionality)
			funcs.add(entry)

		if self.db_pool.configured:
			async with self.db_pool.connection() as db_connection:
				await self.authorizer.setup(db_connection, funcs)

	#------------------------------------------------------------

	async def handle(self, scope, receive, send):

		try:
			request = Request(scope)
			response = Response(send)

			if not self.active:
				response.set_status(401)
				await emit(response)
				return

			if (sent_origin := request.headers.get('origin')) is not None:
				for allowed_cors_origin in self.cors_origins:
					if sent_origin == allowed_cors_origin:
						response.add_header(_cors_allow_origin, sent_origin)
						response.add_header(_cors_allow_credentials, 'true')
						break

			if request.method == "OPTIONS":
				requested_methods = request.headers.get(_cors_req_methods)
				requested_methods = _enlist_value(requested_methods or _all_methods)
				found_methods = list()

				for method in requested_methods:
					found_endpoint = self.registry.find_endpoint(
						method, request.path)

					if found_endpoint is not None:
						found_methods.append(method)

				if 0 == len(found_methods):
					response.set_status(404)
					await emit(response)
					return

				joined_methods = ", ".join(found_methods)
				response.add_header(_cors_allow_methods, joined_methods)

				requested_headers = request.headers.get(_cors_req_headers)
				requested_headers = _enlist_value(requested_headers or list())

				allowed_headers = ([
					header for header in requested_headers
						if header in self.cors_headers
				])

				if len(allowed_headers) > 0:
					joined_headers = ", ".join(allowed_headers)
					response.add_header(_cors_allow_headers,
						joined_headers)

				await emit(response)
				return

			found_endpoint = self.registry.find_endpoint(
				request.method,
				request.path)

			if found_endpoint is None:
				response.set_status(404)
				await emit(response)
				return

			endpoint, path_variables = found_endpoint
			if self.db_pool.configured:
				has_access, validation_outcome = await self.authorizer.validate_access(
					request, endpoint)

			else:
				has_access = True
				validation_outcome = None

			if not has_access:
				if validation_outcome in (
					AuthError.MISSING_TOKEN,
					AuthError.INVALID_TOKEN,
					AuthError.EXPIRED_AUTH,
					AuthError.BLOCKED_USER
				): status = 401

				if validation_outcome is AuthError.NOT_ALLOWED: status = 403
				if validation_outcome is AuthError.DISABLED_ENDPOINT: status = 410

				failure_status = validation_outcome
				response.set_status(status)
				await emit(response)
				return

			auth_data = validation_outcome
			broadcasting = self.server.broadcaster
			handler = endpoint.function

			async with self.db_pool.connection() as db_connection:
				all_args = { 'server': self.server }

				for arg in self.arguments:
					current_value = locals()[arg]
					all_args[arg] = current_value

				await handler(all_args)
				await emit(response)

		except Exception as e:
			Logger.error(f"Error processing request: {e}")
			Logger.error(traceback.format_exc())
			response.set_status(500)
			await emit(response)


__all__ = [
	"HttpHandler"
]

