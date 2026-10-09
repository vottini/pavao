
import os
import asyncio
import functools
from datetime import datetime, timezone
import umapper
import jsonbp

from .logger import Logger
from .exception import PavaoException
from .i18n import ModuleLocalizer
from .utils import error_contents, error_blueprint
from . import predicates

_messages_dir = os.path.join(os.path.dirname(__file__), 'messages')
_localizer = ModuleLocalizer('json', _messages_dir)
_bad_content_type = _localizer.map('BAD_CONTENT_TYPE')
_bad_request_body = _localizer.map('BAD_REQUEST_BODY')

_valid_content_types = (
	'application/json; charset=utf-8',
	'application/json'
)


def _load_blueprint(
	string,
	file,
	root=None,
	array_root=False,
	min_length=0,
	max_length=1024):

	arguments = (string, file)
	if all(value is None for value in arguments):
		msg = "Either 'string' or 'file' parameters must be specified"
		raise PavaoException(msg)

	if all(value is not None for value in arguments):
		msg = "Both 'string' and 'file' parameters were specified; 'string' takes precedence — remove it to use 'file'"
		Logger.warning(msg)

	loaded = (
		jsonbp.load_file(file) if string is None else
		jsonbp.load_string(string))

	return (
		loaded if root is None
		else loaded.choose_root(root, array_root, min_length, max_length)
	)


accept_json_output = { "parsed_json" }
accept_json_params = { "request", "response", "receive" }
accept_json_template = """

@functools.wraps(fnc)
async def wrapped({ALL_PARAMS}):
	global blueprint
	content_type = request.headers.get('content-type')
	if content_type is None or content_type not in _valid_content_types:
		response.set_status(400)
		locale_priority = request.parse_locale_priority()
		payload = {{'error': "BAD_REQUEST", 'description': _bad_content_type.localize(locale_priority), 'timestamp': datetime.now(timezone.utc)}}
		response.set_content('application/json', error_blueprint.serialize(payload).encode())
		return

	received = await receive()
	body = received['body']
	while received['more_body']:
		received = await receive()
		body += received['body']

	try:
		json_content = body.decode()
		success, outcome = blueprint.deserialize(json_content)

	except Exception as e:
		Logger.warning(str(e))
		response.set_status(400)
		locale_priority = request.parse_locale_priority()
		payload = {{'error': "BAD_REQUEST", 'description': _bad_request_body.localize(locale_priority), 'timestamp': datetime.now(timezone.utc)}}
		response.set_content('application/json', error_blueprint.serialize(payload).encode())
		return

	if not success:
		response.set_status(400)
		locale_priority = request.parse_locale_priority()
		payload = {{'error': "BAD_REQUEST", 'description': outcome.localize(locale_priority), 'timestamp': datetime.now(timezone.utc)}}
		response.set_content('application/json', error_blueprint.serialize(payload).encode())
		return

	outcome = umapper.translate_case(outcome, umapper.Case.SNAKE)
	parsed_json = umapper.convert_to_object(outcome)

	all_args = {{
		'parsed_json': parsed_json,
		{CONTEXT}
	}}

	selected_args = list()
	for param_name in {FNC_PARAMS}:
		selected_args.append(all_args[param_name])

	result = await fnc(*selected_args)
	return result

"""


def accepts_json(
	string_blueprint=None,
	file_blueprint=None,
	with_root=None,
	array_root=False,
	min_length=0,
	max_length=1024):

	blueprint = _load_blueprint(
		string_blueprint,
		file_blueprint,
		with_root,
		array_root,
		min_length,
		max_length)

	def wrapper(fnc):
		fnc_nargs = fnc.__code__.co_argcount
		fnc_lvars = fnc.__code__.co_varnames
		fnc_params = fnc_lvars[0:fnc_nargs]

		all_params = (
			(set(fnc_params) - accept_json_output)
			| accept_json_params
		)

		code = accept_json_template.format(
			ALL_PARAMS=",".join(all_params),
			CONTEXT=",".join(map(lambda x : f"'{x}': {x}", all_params)),
			FNC_PARAMS=str(fnc_params)
		)

		namespace = globals().copy()
		scope = locals().copy()

		namespace.update({
			'blueprint': blueprint,
			'fnc': fnc
		})

		exec(code, namespace, scope)
		return scope['wrapped']

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
			Logger.warning(msg)


generates_json_params = { "response" }
generates_json_template = """

@functools.wraps(fnc)
async def wrapped({ALL_PARAMS}):
	all_args = {{ {CONTEXT} }}

	selected_args = list()
	for param_name in {FNC_PARAMS}:
		selected_args.append(all_args[param_name])

	payload = await fnc(*selected_args)
	if payload is None:
		return

	for predicate, blueprint in processed_dispatchers:
		if predicate(response.status):
			serialized = str(blueprint.serialize(payload))
			response.set_content('application/json', serialized.encode())
			return

	payload = {{
		'error': "JSON_SERIALIZATION",
		'description': f'No known serialization for status {{response.status}}',
		"timestamp": datetime.now(timezone.utc)
	}}

	serialized = error_blueprint.serialize(payload)
	response.set_content('application/json', serialized.encode())
	response.set_status(500)

"""

def generates_json(
	dispatchers=None,
	string_blueprint=None,
	file_blueprint=None,
	with_root=None,
	array_root=False,
	min_length=0,
	max_length=1024):

	processed_dispatchers = list()
	if dispatchers is not None:

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
					predicate = lambda status, s=statuses: status in s
					processed_dispatchers.append((predicate, blueprint))
					_warn_unused(rule, 'statuses', ['status'])
					_trial_predicate(predicate)
					continue

				rule_status = rule.get('status')

				if rule_status is None:
					msg = "Either 'predicate', 'statuses' or 'status' must be specified"
					raise PavaoException(msg)

				predicate = lambda status, rs=rule_status: rs == status
				processed_dispatchers.append((predicate, blueprint))
				_trial_predicate(predicate)

		except (KeyError, TypeError):
			msg = f"'dispatchers' must be an iterable, received {type(dispatchers)}"
			raise PavaoException(msg)

	else:
		blueprint = _load_blueprint(
			string_blueprint,
			file_blueprint,
			with_root,
			array_root,
			min_length,
			max_length)

		processed_dispatchers.append((predicates.status_non_error, blueprint))
		processed_dispatchers.append((predicates.status_error, error_blueprint))

	def wrapper(fnc):
		fnc_nargs = fnc.__code__.co_argcount
		fnc_lvars = fnc.__code__.co_varnames
		fnc_params = fnc_lvars[0:fnc_nargs]

		all_params = (
			set(fnc_params)
			| generates_json_params
		)

		code = generates_json_template.format(
			ALL_PARAMS=",".join(all_params),
			CONTEXT=",".join(map(lambda x : f"'{x}': {x}", all_params)),
			FNC_PARAMS=str(fnc_params)
		)

		namespace = globals().copy()
		scope = locals().copy()

		namespace.update({
			'processed_dispatchers': processed_dispatchers,
			'fnc': fnc
		})

		exec(code, namespace, scope)
		return scope['wrapped']

	return wrapper


def field_present(converted_dict, fieldName):
	return hasattr(converted_dict, fieldName)

#-------------------------------------------------------------------------------

__all__ = [
	"accepts_json",
	"generates_json",
	"error_contents",
	"error_blueprint",
	"field_present"
]

