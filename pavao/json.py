
import asyncio
import functools
import jsonbp

from .logger import Logger

_valid_content_types = (
	'application/json; charset=utf-8'
	'application/json'
)


def acceptsJson(string=None, file=None):
	needed_params = (string, file)
	if all(value is None for value in needed_params):
		msg = "acceptsJson() needs to receive either 'string' or 'file' parameter"
		raise Exception(msg)

	exclusive_params = needed_params
	if all(value is not None for value in exclusive_params):
		msg = "acceptsJson() received both 'string' and 'file' parameters, using 'string'"
		Logger.warning(msg)

	blueprint = (
		jsonbp.load(file) if string is None
		else jsonbp.loads(string))

	def wrapper(fnc):
		@functools.wraps(fnc)
		async def wrapped(
			request,
			path_variables,
			db_connection,
			response,
			receive):

			content_type = request.headers.get('content-type')
			if content_type is None or content_type not in _valid_content_types:
				response.set_status(400)
				return None

			received = await receive()
			payload = received['body']
			while received['more_body']:
				received = await receive()
				payload += received['body']

			json_content = payload.decode()
			success, outcome = blueprint.deserialize(json_content)

			if not success:
				response.set_status(400)
				response.set_plain_text(str(outcome))
				return None

			all_args = {
				'request': request,
				'path_variables': path_variables,
				'db_connection': db_connection,
				'response': response,
				'receive': receive,
				'parsed_json': outcome
			}

			fnc_nargs = fnc.__code__.co_argcount
			fnc_lvars = fnc.__code__.co_varnames
			fnc_params = fnc_lvars[0:fnc_nargs]

			selected_args = list()
			for param_name in fnc_params:
				selected_args.append(all_args[param_name])

			result = await fnc(*selected_args)
			return result

		return wrapped

	return wrapper


#def generates()
#	pass

#-------------------------------------------------------------------------------

__all__ = [
	"acceptsJson"
]

