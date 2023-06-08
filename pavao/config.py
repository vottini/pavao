
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

def requiresDefinition(schema):
	if isinstance(schema, list): return False
	if isinstance(schema, type): return True

	if isinstance(schema, dict):
		for key, value in schema.items():
			if isinstance(value, type):
				return True
			
			if isinstance(value, dict):
				if requiresDefinition(value):
					return True

	return False


def processConfig(configured, entry, schema):

	# first look if it expects a list of items
	# and if yes then just map each item recursively

	if isinstance(schema, list):
		if len(schema) != 1:
			msg = f"List on schema ({entry}) needs to have only one element"
			raise ConfigException(msg)

		if not isinstance(configured, list):
			msg = f"'{entry}' needs to be a list"
			raise ConfigException(msg)

		innerSchema = schema[0]
		if not isinstance(innerSchema, (type, dict)):
			msg = f"Bad description for list in schema ({entry}), needs to be a type or a dict"
			raise ConfigException(msg)

		result = list()
		for idx, value in enumerate(configured):
			innerResult = processConfig(value, f"{entry}[{idx}]", innerSchema)
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
		if requiresDefinition(schema):
			msg = f"{entry} is not defined and has no defaults"
			raise ConfigException(msg)
	
		return schema

	defaultValue = schema
	requiredType = defaultValue if isinstance(defaultValue, type) else type(defaultValue)

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
				return requiredType(retrievedValue)

			except ValueError as e:
				msg = f"Unable to convert '{retrievedValue}' to {requiredType}"
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

	if not isinstance(defaultValue, dict):
		if isinstance(configured, requiredType):
			return configured

		msg = f"'{entry}' expects {requiredType} but got {type(configured)}"
		raise ConfigException(msg)

	# finally, if the schema is a dictionary
	# iterate over its keys and values, recursively
	# retrieving the final definitions

	result = dict()
	for key, innerSchema in defaultValue.items():
		innerConfigured = configured.get(key)
	
		result[key] = processConfig(
			innerConfigured,
			f"{entry}.{key}",
			innerSchema)

	return result

#-------------------------------------------------------------------------------

class _Settings:
	def __init__(self, settings):
		self.settings = settings

	def getSetting(self, entry, schema):
		components = entry.split('.') 
		node = self.settings
	
		counter = 0
		while node != None and counter < len(components):
			node = node.get(components[counter])
			counter += 1
	
		if None != node: return processConfig(node, entry, schema)
		return None


def loadSettings(configFile="application.yml"):
	Logger.info(f"Loading configuration file '{configFile}'")

	try:
		with open(configFile) as config_fd:
			flattened = yaml.safe_load(config_fd)
			structured = unflatten(flattened)
			return _Settings(structured)

	except OSError as e:
		cause = f"Unable to read configuration file '{configFile}'"
		raise ConfigException(cause) from None
	
	except yaml.error.MarkedYAMLError as e:
		cause = f"Unable to parse YAML: {e}"
		raise ConfigException(cause) from None

#-------------------------------------------------------------------------------

__all__ = [
	'ConfigException',
	'loadSettings'
]

