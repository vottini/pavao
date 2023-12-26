
import os
import yaml
import re

VAR_PATTERN = re.compile(r"\$\{(\w+)\}")

from .logger import Logger
from .exception import PavaoException
class ConfigException(PavaoException):
	pass

#-------------------------------------------------------------------------------

def unflatten(config):
	separator = '.'
	result = dict()

	for key, value in config.items():
		if not separator in key:
			result[key] = value

		else:
			level, sublevels = key.split(separator, maxsplit=1)
			container = result.get(level, config.get(level, dict()))
			container[sublevels] = value
			result[level] = container

	for key, subconfig in result.items():
		if isinstance(subconfig, dict):
			result[key] = unflatten(subconfig)

	return result

#-------------------------------------------------------------------------------

def requires_definition(schema):
	if isinstance(schema, list): return False
	if isinstance(schema, type): return True

	if isinstance(schema, dict):
		for key, value in schema.items():
			if isinstance(value, type):
				return True

			if isinstance(value, dict):
				if requires_definition(value):
					return True

	return False


def process_config(configured, entry, schema):

	# first look if it expects a list of items
	# and if yes then just map each item recursively

	if isinstance(schema, list):
		if len(schema) != 1:
			msg = f"List on schema ({entry}) needs to have only one element"
			raise ConfigException(msg)

		configured = configured if configured is not None else list()
		if not isinstance(configured, list):
			msg = f"'{entry}' needs to be a list"
			raise ConfigException(msg)

		inner_schema = schema[0]
		if not isinstance(inner_schema, (type, dict)):
			msg = f"Bad description for list in schema ({entry}), needs to be a type or a dict"
			raise ConfigException(msg)

		result = list()
		for idx, value in enumerate(configured):
			innerResult = process_config(value, f"{entry}[{idx}]", inner_schema)
			result.append(innerResult)

		return result

	if isinstance(configured, list):
		msg = f"'{entry}' needs to be a single element, got list"
		raise ConfigException(msg)

	# if nothing was configured under this entry,
	# check whether it has any required values to be set,
	# and if possible just return the schema if it is
	# comprised only of default values

	if None == configured:
		if requires_definition(schema):
			msg = f"{entry} is not defined and has no defaults"
			raise ConfigException(msg)

		return schema

	default_value = schema
	required_type = (default_value
		if isinstance(default_value, type)
		else type(default_value))

	# when the assigned value matches a enviroment
	# variable format, try to retrieve and convert it to
	# the expected type

	if isinstance(configured, str):
		varMatch = VAR_PATTERN.search(configured)

		if None != varMatch:
			varName = varMatch.group(1)

			if not varName in os.environ:
				msg = f"Environment variable '${{{varName}}}' not found while processing '{entry}'"
				raise ConfigException(msg)

			try:
				retrievedValue = os.environ.get(varName)
				return required_type(retrievedValue)

			except ValueError as e:
				msg = f"Unable to convert '{retrievedValue}' to {required_type}"
				raise ConfigException(msg) from None

	# if no default is set, (only the expected type
	# is defined), check if the assigned value is
	# coherent and just return it

	if isinstance(schema, type):
		if isinstance(configured, schema):
			return configured

		msg = f"'{entry}' expects {schema} but got {type(configured)}"
		raise ConfigException(msg)

	# otherwise (default is set) and it is a
	# simple type, just check its type and return
	# accordingly

	if not isinstance(default_value, dict):
		if isinstance(configured, required_type):
			return configured

		msg = f"'{entry}' expects {required_type} but got {type(configured)}"
		raise ConfigException(msg)

	# finally, if the schema is a dictionary
	# iterate over its keys and values, recursively
	# retrieving the final definitions

	result = dict()
	for key, inner_schema in default_value.items():
		inner_configured = configured.get(key)

		result[key] = process_config(
			inner_configured,
			f"{entry}.{key}",
			inner_schema)

	return result

#-------------------------------------------------------------------------------

class _Settings:
	def __init__(self, settings):
		self.settings = settings

	def get_setting(self, entry, schema):
		components = entry.split('.')
		node = self.settings

		counter = 0
		while node != None and counter < len(components):
			node = node.get(components[counter])
			counter += 1

		if None != node: return process_config(node, entry, schema)
		return None


def load_settings(config_file="application.yml"):
	Logger.info(f"Loading configuration file '{config_file}'")

	try:
		with open(config_file) as config_fd:
			flattened = yaml.safe_load(config_fd)
			structured = unflatten(flattened)
			return _Settings(structured)

	except OSError as e:
		cause = f"Unable to read configuration file '{config_file}'"
		raise ConfigException(cause) from None

	except yaml.error.MarkedYAMLError as e:
		cause = f"Unable to parse YAML: {e}"
		raise ConfigException(cause) from None

#-------------------------------------------------------------------------------

import asyncio
import builtins
import collections
import re

list_pattern = re.compile(r"\[([^\]]+)\]")
get_query = "SELECT type, value FROM pavao.parameters WHERE name = $1"

upsert_query = """

	INSERT INTO
		pavao.parameters (name, type, value)
		VALUES ($1, $2, $3)

		ON CONFLICT (name) DO UPDATE
			SET type = excluded.type,
				value = excluded.value;

"""

class PersistedSettings:
	def __init__(self, db_pool):
		self.listeners = dict()
		self.db_pool = db_pool


	async def get(self, name):
		async with self.db_pool.connection() as db_connection:
			row = await db_connection.fetchrow(get_query, name)
			if row is None: return None

			typ, value = row
			list_search = list_pattern.search(value)
			ctor = getattr(builtins, typ)

			if list_search is not None:
				list_content = list_search.group(1)
				return [ ctor(vle) for vle in list_content.split("::") ]

			return ctor(value)


	def monitor(self, name, callback):
		key_listeners = self.listeners.get(name, list())
		key_listeners.append(callback)
		self.listeners[name] = key_listeners


	async def set(self, name, value):
		value_type = type(value).__name__
		original_value = value

		if isinstance(value, collections.abc.Sequence) and not isinstance(value, str):
			value_type = type(value[0]).__name__
			str_values = map(str, value)
			value = f"[{'::'.join(str_values)}]"

		async with self.db_pool.connection() as db_connection:
			await db_connection.execute(upsert_query,
				name, value_type, str(value))

		listeners = self.listeners.get(name, list())
		for listener in listeners:
			listener(original_value)


__all__ = [
	'ConfigException',
	'PersistedSettings',
	'load_settings'
]

