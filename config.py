
import os
import yaml
import re

NO_DEFAULT = "__undefined__"
DEFAULT_FILE = "application.yml"
VAR_PATTERN = re.compile(r"\$\{(\w+)\}")

class ConfigException(Exception):
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

configFile = os.environ.get("PAVAO_CONFIG", DEFAULT_FILE)
__config = None

try:
	with open(configFile) as config_fd:
		flattened = yaml.safe_load(config_fd)
		__config = unflatten(flattened)

except yaml.error.MarkedYAMLError as e:
	print("Error parsing configuration file")
	print(f"What went wrong: {e}")

except OSError as e:
	print(f"Unable to read configuration from file '{configFile}'")
	print("Make sure it exists and can be read")

if None == __config:
	msg = "Unable to load configuration, aborting..." 
	raise ConfigException(msg)

#-------------------------------------------------------------------------------

def requiresDefinition(schema):
	if isinstance(schema, list): return False
	if isinstance(schema, type): return True

	if isinstance(schema, dict):
		for key, value in schema.items():
			if NO_DEFAULT == value:
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
	# retrieving the final values

	result = dict()
	for key, innerSchema in defaultValue.items():
		innerConfigured = configured.get(key)
	
		result[key] = processConfig(
			innerConfigured,
			f"{entry}.{key}",
			innerSchema)

	return result


def obtainConfig(entry, schema):
	components = entry.split('.') 
	node = __config

	counter = 0
	while node != None and counter < len(components):
		node = node.get(components[counter])
		counter += 1

	if None != node: return processConfig(node, entry, schema)
	return None

#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------

databaseSchema = {
	"name": NO_DEFAULT,
	"user": NO_DEFAULT,

	"address": {
		"port": 3322,

		"ip": {
			"hostname": NO_DEFAULT,
			"version": 4
		}
	},
}

proxiesSchema = [
	str
]

servicesSchema = [{
	"name": NO_DEFAULT,
	"url": NO_DEFAULT,
	"prefix": "/api"
}]

tests = [
	("pavao.database", databaseSchema),
	("pavao.database.user", str),
	("proxies", proxiesSchema),
	("services", servicesSchema)
]

for test in tests:
	result = obtainConfig(*test)
	print(f"result: {result}")

