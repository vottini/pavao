
import collections
import functools

from .exception import PavaoException
from .i18n import Internationalization

from .loader import path_to
internationalization = Internationalization(
	path_to('messages')
)

def accepts_parameters(parameter_dict):
	specs = dict()

	for name, value in parameter_dict.items():
		if isinstance(value, collections.abc.Sequence) and not isinstance(value, str):
			if len(value) != 1 or not isinstance(value[0], type):
				msg = f"list especification needs to have exactly one element and it needs to be a type"
				raise PavaoException(msg)

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

		specs[name] = (
			as_list,
			default_value,
			ctor
		)

	def wrapper(fnc):
		fnc_nargs = fnc.__code__.co_argcount
		fnc_lvars = fnc.__code__.co_varnames
		fnc_params = fnc_lvars[0:fnc_nargs]

		@functools.wraps(fnc)
		async def wrapped(
			request,
			path_variables,
			db_connection,
			auth_data,
			response,
			receive,
			broadcasting):

			parameters = dict()
			for name, value in parameter_dict.items():
				as_list, default_value, ctor = specs[name]

				if not name in request.params:
					if default_value is None:
						localizer = internationalization.create_localizer(request)
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
					localizer = internationalization.create_localizer(request)
					localizer.assign_response_error(response, "PARAMS_INVALID")
					response.set_status(400)
					return

			all_args = {
				'request': request,
				'path_variables': path_variables,
				'db_connection': db_connection,
				'auth_data': auth_data,
				'response': response,
				'receive': receive,
				'parameters': parameters,
				'broadcasting': broadcasting
			}

			selected_args = list()
			for param_name in fnc_params:
				selected_args.append(all_args[param_name])

			result = await fnc(*selected_args)
			return result

		return wrapped

	return wrapper

#------------------------------------------------------------------------------

__all__ = [
	"accepts_parameters"
]

