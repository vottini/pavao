
import asyncio
import functools
from datetime import datetime, timezone
import jsonbp

from .logger import Logger
from .exception import PavaoException
from .mapper import convert_to_object
from . import predicates

error_contents = '''

	root {
		error: string,
		description: string,
		timestamp: instant
	}

'''

error_blueprint = jsonbp.loadString(error_contents)

_valid_content_types = (
	'application/json; charset=utf-8'
	'application/json'
)


def _load_blueprint(string, file, root=None):
	arguments = (string, file)
	if all(value is None for value in arguments):
		msg = "Either 'string' or 'file' parameters must be specified"
		raise PavaoException(msg)

	if all(value is not None for value in arguments):
		msg = "Both 'string' and 'file' parameters were specified, using 'string'"
		Logger.warning(msg)

	loaded = (
		jsonbp.loadFile(file) if string is None else
		jsonbp.loadString(string))

	return (
		loaded if root is None
		else loaded.chooseRoot(root)
	)


def accepts_json(
	string_blueprint=None,
	file_blueprint=None,
	with_root=None):

	blueprint = _load_blueprint(
		string_blueprint,
		file_blueprint,
		with_root)

	def wrapper(fnc):
		fnc_nargs = fnc.__code__.co_argcount
		fnc_lvars = fnc.__code__.co_varnames
		fnc_params = fnc_lvars[0:fnc_nargs]

		@functools.wraps(fnc)
		async def wrapped(
			handler,
			server,
			request,
			path_variables,
			db_connection,
			broadcasting,
			auth_data,
			response,
			receive):

			content_type = request.headers.get('content-type')
			if content_type is None or content_type not in _valid_content_types:
				response.set_status(400)

				return {
					'error': "BAD_REQUEST",
					'description': 'Bad content type',
					'timestamp': datetime.now(timezone.utc)
				}

			received = await receive()
			payload = received['body']
			while received['more_body']:
				received = await receive()
				payload += received['body']

			try:
				json_content = payload.decode()
				success, outcome = blueprint.deserialize(json_content)

			except Exception:
				response.set_status(400)

				return {
					'error': "BAD_REQUEST",
					'description': 'Unable to decode content',
					'timestamp': datetime.now(timezone.utc)
				}

			if not success:
				response.set_status(400)

				return {
					'error': "BAD_REQUEST",
					'description': str(outcome),
					'timestamp': datetime.now(timezone.utc)
				}

			all_args = {
				'handler': handler,
				'server': server,
				'request': request,
				'path_variables': path_variables,
				'db_connection': db_connection,
				'broadcasting': broadcasting,
				'auth_data': auth_data,
				'response': response,
				'receive': receive,
				'parsed_json': convert_to_object(outcome)
			}

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


def generates_json(
	dispatchers=None,
	string_blueprint=None,
	file_blueprint=None,
	with_root=None):

	processed_dispatchers = list()

	if dispatchers is None:
		blueprint = _load_blueprint(string_blueprint, file_blueprint, with_root)
		processed_dispatchers.append((predicates.status_non_error, blueprint))
		processed_dispatchers.append((predicates.status_error, error_blueprint))

	else:
		try:
			for rule in dispatchers:
				if rule.get('string') is error_contents:
					blueprint = error_blueprint

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
		fnc_nargs = fnc.__code__.co_argcount
		fnc_lvars = fnc.__code__.co_varnames
		fnc_params = fnc_lvars[0:fnc_nargs]

		@functools.wraps(fnc)
		async def wrapped(
			handler,
			server,
			request,
			path_variables,
			db_connection,
			broadcasting,
			auth_data,
			response,
			receive):

			all_args = {
				'handler': handler,
				'server': server,
				'request': request,
				'path_variables': path_variables,
				'db_connection': db_connection,
				'broadcasting': broadcasting,
				'auth_data': auth_data,
				'response': response,
				'receive': receive
			}

			selected_args = list()
			for param_name in fnc_params:
				selected_args.append(all_args[param_name])

			payload = await fnc(*selected_args)
			if payload is None:
				return

			for predicate, blueprint in processed_dispatchers:
				if predicate(response.status):
					serialized = str(blueprint.serialize(payload))
					response.set_content('application/json', serialized.encode())
					return

			payload = {
				'error': "JSON_SERIALIZATION",
				'description': f'No known serialization for status {response.status}',
				"timestamp": datetime.now(timezone.utc)
			}

			serialized = error_blueprint.serialize(payload)
			response.set_content('application/json', serialized.encode())
			response.set_status(500)

		return wrapped

	return wrapper


def has_optional_field(converted_dict, fieldName):
	return hasattr(converted_dict, fieldName)

#-------------------------------------------------------------------------------

__all__ = [
	"accepts_json",
	"generates_json",
	"error_contents",
	"error_blueprint",
	"has_optional_field"
]

