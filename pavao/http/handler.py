
import asyncio
import inspect
import traceback

from ..logger import Logger
from ..registry import Registry

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
	def __init__(self, server, broadcasting):
		self.server = server
		self.broadcasting = broadcasting
		self.registry = Registry()
		self.active = True

		self.cors_origins = list()
		self.cors_headers = set([
			'accept',
			'accept-language',
			'content-language',
			'content-type',
			'authorization',
		])


	def deactivate(self):
		self.active = False

	#------------------------------------------------------------

	async def init(self, loaded_settings):
		http_settings = loaded_settings.get_setting(
			"pavao.http",
			_http_schema)

		if http_settings is not None:
			cors_settings = http_settings.get('CORS', dict())
			self.cors_headers.update(cors_settings.get('headers', list()))
			self.cors_origins = cors_settings.get('origins', list())


	async def update_registry(self, registry):
		self.registry = registry
		#funcs = set()

		#for endpoint in registry.list_endpoints():
		#	if endpoint.functionality is None: continue
		#	entry = (endpoint.package, endpoint.functionality)
		#	funcs.add(entry)

		#if self.db_pool.configured:
		#	async with self.db_pool.connection() as db_connection:
		#		await self.authorizer.setup(db_connection, funcs)

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
					found_endpoint = self.registry.find_endpoint(method, request.path)
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

			http_context = {
				'server': self.server,
				'request': request,
				'response': response,
				'endpoint_specs': endpoint.all_specs,
				'path_variables': path_variables,
				'broadcasting': self.broadcasting,
				'receive': receive
			}

			await endpoint.function(http_context)
			await emit(response)

		except Exception as e:
			Logger.error(f"Error processing request: {e}")
			Logger.error(traceback.format_exc())
			response.set_status(500)
			await emit(response)


__all__ = [
	"HttpHandler"
]

