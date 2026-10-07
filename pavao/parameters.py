
import collections
import functools

from .exception import PavaoException
from .i18n import Internationalization

from .loader import path_to

internationalization = Internationalization(path_to('messages'))

accepts_parameters_output = { "parameters" }
accepts_parameters_params = { "request", "response" }
accepts_parameters_template = """

@functools.wraps(fnc)
async def wrapped({ALL_PARAMS}):

	parameters = dict()
	for name, value in parameter_dict.items():
		as_list, default_value, ctor = parameter_specs[name]

		if not name in request.params:
			if default_value is None:
				accepted_languages = request.parse_locale_priority()
				localizer = internationalization.create_localizer(accepted_languages)
				localizer.assign_response_error(response, "PARAMS_MISSING")
				response.set_status(400)
				return

			parameters[name] = default_value
			continue

		try:
			raw_value = request.params[name]
			parameters[name] = (
				[ ctor(element) for element in raw_value.split(',') ] if as_list
				else ctor(raw_value)
			)

		except Exception as e:
			accepted_languages = request.parse_locale_priority()
			localizer = internationalization.create_localizer(accepted_languages)
			localizer.assign_response_error(response, "PARAMS_INVALID")
			response.set_status(400)
			return

	all_args = {{
		'parameters': parameters,
		{CONTEXT}
	}}

	selected_args = list()
	for param_name in {FNC_PARAMS}:
		selected_args.append(all_args[param_name])

	result = await fnc(*selected_args)
	return result

"""

def accepts_parameters(parameter_dict):
	parameter_specs = dict()

	for name, value in parameter_dict.items():
		if (isinstance(value, collections.abc.Sequence)
			and not isinstance(value, str)):

			if len(value) != 1 or not isinstance(value[0], type):
				raise PavaoException(
					"list specification needs to have exactly " +
					"one element and it needs to be a type"
				)

			ctor = value[0]
			default_value = None
			as_list = True

		else:
			as_list = False
			if isinstance(value, type):
				default_value = None
				ctor = value

			else:
				default_value = value
				ctor = type(default_value)

		parameter_specs[name] = (
			as_list,
			default_value,
			ctor
		)

	def wrapper(fnc):
		fnc_nargs = fnc.__code__.co_argcount
		fnc_lvars = fnc.__code__.co_varnames
		fnc_params = fnc_lvars[0:fnc_nargs]

		all_params = (
			(set(fnc_params) - accepts_parameters_output)
			| accepts_parameters_params
		)

		code = accepts_parameters_template.format(
			ALL_PARAMS=",".join(all_params),
			CONTEXT=",".join(map(lambda x : f"'{x}': {x}", all_params)),
			FNC_PARAMS=str(fnc_params)
		)

		namespace = globals().copy()
		scope = locals().copy()

		namespace.update({
			'parameter_dict': parameter_dict,
			'parameter_specs': parameter_specs,
			'fnc': fnc
		})

		exec(code, namespace, scope)
		return scope['wrapped']

	return wrapper

#------------------------------------------------------------------------------

__all__ = [
	"accepts_parameters"
]
