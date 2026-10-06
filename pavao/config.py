
import os
import re
import yaml

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
		if separator not in key:
			result[key] = dict(value) if isinstance(value, dict) else value

	for key, value in config.items():
		if separator in key:
			level, sublevels = key.split(separator, maxsplit=1)
			if level not in result:
				result[level] = dict()
			elif not isinstance(result[level], dict):
				raise ConfigException(f"Key '{level}' cannot be both a value and a namespace")
			result[level][sublevels] = value

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


def _resolve_env_vars(configured, entry, required_type):
	var_names = VAR_PATTERN.findall(configured)
	if not var_names:
		return None

	for var_name in var_names:
		if var_name not in os.environ:
			raise ConfigException(
				f"Environment variable '${{{var_name}}}' not found while processing '{entry}'"
			)

	substituted = VAR_PATTERN.sub(lambda m: os.environ[m.group(1)], configured)

	try:
		return required_type(substituted)
	except (ValueError, TypeError):
		raise ConfigException(
			f"Unable to convert '{substituted}' to {required_type}"
		) from None


def process_config(configured, entry, schema):

	if isinstance(schema, list):
		if len(schema) != 1:
			raise ConfigException(f"List schema for '{entry}' must have exactly one element")

		configured = configured if configured is not None else list()
		if not isinstance(configured, list):
			raise ConfigException(f"'{entry}' must be a list")

		inner_schema = schema[0]
		if not isinstance(inner_schema, (type, dict)):
			raise ConfigException(f"List schema element for '{entry}' must be a type or dict")

		return [
			process_config(v, f"{entry}[{i}]", inner_schema)
			for i, v in enumerate(configured)
		]

	if isinstance(configured, list):
		raise ConfigException(f"'{entry}' must be a single value, got list")

	if configured is None:
		if requires_definition(schema):
			raise ConfigException(f"'{entry}' is required but not set")
		return schema

	required_type = schema if isinstance(schema, type) else type(schema)

	if isinstance(configured, str):
		resolved = _resolve_env_vars(configured, entry, required_type)
		if resolved is not None:
			return resolved

	if isinstance(schema, type):
		if isinstance(configured, schema):
			return configured
		raise ConfigException(f"'{entry}' expects {schema} but got {type(configured)}")

	if not isinstance(schema, dict):
		if isinstance(configured, required_type):
			return configured
		raise ConfigException(f"'{entry}' expects {required_type} but got {type(configured)}")

	return {
		key: process_config(configured.get(key), f"{entry}.{key}", inner_schema)
		for key, inner_schema in schema.items()
	}

#-------------------------------------------------------------------------------

class _Settings:
	def __init__(self, settings):
		self.settings = settings

	def get_setting(self, entry, schema):
		components = entry.split('.')
		node = self.settings

		for component in components:
			if not isinstance(node, dict):
				node = None
				break
			node = node.get(component)

		if node is None:
			return None if requires_definition(schema) else schema

		return process_config(node, entry, schema)


def load_settings(config_file, is_default=False):
	if is_default and not os.path.isfile(config_file):
		return _Settings(None)

	try:
		Logger.info(f"Loading configuration file '{config_file}'")
		with open(config_file) as f:
			raw = yaml.safe_load(f)
			structured = unflatten(raw) if raw is not None else dict()
			return _Settings(structured)

	except OSError:
		raise ConfigException(
			f"Unable to read configuration file '{config_file}'"
		) from None

	except yaml.error.MarkedYAMLError as e:
		raise ConfigException(f"Unable to parse YAML: {e}") from None

#-------------------------------------------------------------------------------

__all__ = [
	'ConfigException',
	'load_settings'
]
