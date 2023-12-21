
import humps

class Case:
	CAMEL = 1
	SNAKE = 2
	PASCAL = 3

_transforms = {
	Case.CAMEL: humps.camelize,
	Case.SNAKE: lambda x : humps.decamelize(humps.camelize(x)),
	Case.PASCAL: humps.pascalize,
}

def _createCaseMapping(fields, outputCase):
	method = _transforms[outputCase]
	mapping = dict()

	for field in fields:
		mappedField = method(field)
		mapping[mappedField] = field

	return mapping


def translate_case(value, desired_case):
	if isinstance(value, list):
		result = list()

		for item in value:
			translated = translate_case(item, desired_case)
			result.append(translated)

		return result

	if not isinstance(value, dict):
		return value

	dictionary = value
	mapping = _createCaseMapping(dictionary.keys(),
		desired_case)

	convertedDict = dict()
	for outputKey, inputKey in mapping.items():
		inputContent = dictionary[inputKey]

		if isinstance(inputContent, dict):
			inputContent = translate_case(inputContent,
				desired_case)

		if isinstance(inputContent, list):
			translatedValues = list()

			for item in inputContent:
				translated = translate_case(item, desired_case)
				translatedValues.append(translated)

			inputContent = translatedValues

		convertedDict[outputKey] = inputContent

	return convertedDict

#-------------------------------------------------------------------------------

_compound_types = (
	dict,
	list,
	tuple
)

class _convertedDict:
	def __init__(self, dictionary):
		compound = dict()
		sane = dict()

		for key, value in dictionary.items():
			dst = compound if isinstance(value, _compound_types) else sane
			dst[key] = value

		for key, value in compound.items():
			sane[key] = convert_to_object(value)

		self.__dict__.update(sane)


def convert_to_object(value):
	if isinstance(value, dict):
		return _convertedDict(value)

	if isinstance(value, list):

		return [
			convert_to_object(element)
			for element in value
		]

	return value


def assemble_dicts(*base, **named):
	result = dict()

	for entry in base:
		for key, value in entry.items():
			if value is not None:
				result[key] = value

	for field, entry in named.items():
		if isinstance(entry, list):
			scoped = list()

			for item in entry:
				assembled = assemble_dicts(item)
				scoped.append(assembled)

			result[field] = scoped

		elif isinstance(entry, dict):
			scoped = dict()

			for key, value in entry.items():
				if value is not None:
					scoped[key] = value

			result[field] = scoped

		else:
			result[field] = entry

	mapped = translate_case(result, Case.CAMEL)
	return mapped

#-------------------------------------------------------------------------------

__all__ = [
	"Case",
	"translate_case",
	"convert_to_object",
	"has_optional_field",
	"assemble_dicts"
]

