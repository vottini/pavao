
import asyncio
import functools
import jsonbp

from .logger import Logger
from .exception import PavaoException
from . import predicates

error_blueprint = '''

root {
	error: string,
	optional description: string
}

'''

_error_bp = jsonbp.loadString(error_blueprint)

_valid_content_types = (
	'application/json; charset=utf-8'
	'application/json'
)


def _load_blueprint(string, file):
	arguments = (string, file)
	if all(value is None for value in arguments):
		msg = "Either 'string' or 'file' parameters must be specified"
		raise PavaoException(msg)

	if all(value is not None for value in arguments):
		msg = "Both 'string' and 'file' parameters were specified, using 'string'"
		Logger.warning(msg)

	return (
		jsonbp.loadFile(file) if string is None else
		jsonbp.loadString(string))


def acceptsJson(string=None, file=None):
	blueprint = _load_blueprint(string, file)

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
				return { 'error': 'Bad content type'}

			received = await receive()
			payload = received['body']
			while received['more_body']:
				received = await receive()
				payload += received['body']

			json_content = payload.decode()
			success, outcome = blueprint.deserialize(json_content)

			if not success:
				response.set_status(400)
				return { 'error': str(outcome) }

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

#-------------------------------------------------------------------------------

def _trial_predicate(predicate):
	try: predicate(200)
	except Exception as e:
		msg = f"predicate is not valid: {e}"
		raise PavaoException(msg)


def _warn_unused(container, used, candidates):
	for candidate in candidates:
		if candidate in container:
			msg = f"'{candidate}' specified, but '{used}' takes precedence"
			pavao.Logger.warning(msg)


def generatesJson(dispatchers=None, string=None, file=None):
	processed_dispatchers = list()

	if dispatchers is None:
		blueprint = _load_blueprint(string, file)
		processed_dispatchers.append((predicates.status_non_error, blueprint))
		processed_dispatchers.append((predicates.status_error, _error_bp))

	else:
		try:
			for rule in dispatchers:
				if rule.get('string') is error_blueprint:
					blueprint = _error_bp

				else:
					blueprint = _load_blueprint(
						rule.get('string'),
						rule.get('file'))

				if 'predicate' in rule:
					predicate = rule['predicate']
					processed_dispatchers.append((predicate, blueprint))
					_warn_unused(rule, 'predicate', ['statuses', 'status'])
					_trial_predicate(predicate)
					continue

				if 'statuses' in rule:
					statuses = rule['statuses']
					predicate = lambda status: status in statuses
					processed_dispatchers.append((predicate, blueprint))
					_warn_unused(rule, 'statuses', ['status'])
					_trial_predicate(predicate)
					continue

				rule_status = rule.get('status')

				if rule_status is None:
					msg = "Either 'predicate', 'statuses' or 'status' must be specified"
					raise PavaoException(msg)

				predicate = lambda status : rule_status == status
				processed_dispatchers.append((predicate, blueprint))
				_trial_predicate(predicate)

		except KeyError:
			msg = f"'dispatchers' must be an iterable, received {type(dispatchers)}"
			raise PavaoException(msg)

	def wrapper(fnc):
		@functools.wraps(fnc)
		async def wrapped(
			request,
			path_variables,
			db_connection,
			response,
			receive):

			all_args = {
				'request': request,
				'path_variables': path_variables,
				'db_connection': db_connection,
				'response': response,
				'receive': receive
			}

			fnc_nargs = fnc.__code__.co_argcount
			fnc_lvars = fnc.__code__.co_varnames
			fnc_params = fnc_lvars[0:fnc_nargs]

			selected_args = list()
			for param_name in fnc_params:
				selected_args.append(all_args[param_name])

			payload = await fnc(*selected_args)
			for predicate, blueprint in processed_dispatchers:
				if predicate(response.status):
					serialized = blueprint.serialize(payload)
					response.set_content('application/json', serialized.encode())
					return

			payload = {'error': f'No known serialization for status {response.status}'}
			response.set_content('application/json', _error_bp.serialize(payload).encode())
			response.set_status(500)

		return wrapped

	return wrapper

#-------------------------------------------------------------------------------

__all__ = [
	"acceptsJson",
	"generatesJson",
	"error_blueprint"
]

