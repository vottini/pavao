
import asyncio
import inspect
import os

#-------------------------------------------------------------------------------

def adapter(fnc):
	fnc_nParams = fnc.__code__.co_argcount
	fnc_localVars = fnc.__code__.co_varnames
	fnc_params = fnc_localVars[0:fnc_nParams]

	utilized_params = list()
	for param_name in fnc_params:
		utilized_params.append(param_name)

	is_awaitable = inspect.iscoroutinefunction(fnc)

	async def wrapped_call(variables):
		selected_args = [ variables[param] for param in utilized_params ]
		if is_awaitable: return await fnc(*selected_args)
		else: return fnc(*selected_args)

	return wrapped_call

#-------------------------------------------------------------------------------

__all__ = [
	"adapter"
]

