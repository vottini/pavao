
import os
import yaml
import re

NO_DEFAULT = "__undefined__"
DEFAULT_CONFIGURATION = "application.yml"
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

configFile = os.environ.get("PAVAO_CONFIG", DEFAULT_CONFIGURATION)
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

def hasRequiredDefinitions(schema):
	if isinstance(schema, list):
		return False

	for key, value in schema.items():
		if NO_DEFAULT == value:
			return True

		if isinstance(value, dict):
			if hasRequiredDefinitions(value):
				return True

	return False


def obtainConfig(node, entry, schema):
	configured = node.get(entry)

	if None == configured:
		if hasRequiredDefinitions(schema):
			msg = f"Entry '{entry}' is absent but has fields that need definition"
			raise ConfigException(msg)
	
		return schema

	if isinstance(schema, list):
		return configured
	
	result = dict()
	for key, innerSchema in schema.items():
		if isinstance(innerSchema, dict):
			result[key] = obtainConfig(configured, key, innerSchema)
			continue
	
		innerConfigured = configured.get(key)

		if None == innerConfigured:
			if innerSchema == NO_DEFAULT:
				msg = f"Field '{key}' needs to be defined"
				raise ConfigException(msg)
	
			result[key] = innerSchema
			continue
	
		if isinstance(innerConfigured, str):
			varMatch = VAR_PATTERN.search(innerConfigured)
	
			if None != varMatch:
				varName = varMatch.group(1)
	
				if not varName in os.environ:
					msg = f"Environment variable '${{{varName}}}' not found"
					raise ConfigException(msg)
	
				result[key] = os.environ.get(varName)
				continue
	
		result[key] = innerConfigured

	return result

#-------------------------------------------------------------------------------

databaseSchema = {
	"name": NO_DEFAULT,
	"user": NO_DEFAULT,

	"address": {
		"port": NO_DEFAULT,

		"ip": {
			"hostname": NO_DEFAULT,
			"version": 4
		}
	}
}

pavaoConfig = __config.get("pavao")

result = obtainConfig(
	pavaoConfig,
	"database",
	databaseSchema)

print(f"result: {result}")

proxiesSchema = [
]

result = obtainConfig(
	pavaoConfig,
	"proxies",
	proxiesSchema)

print(f"result: {result}")

