
import asyncio
import functools
import inspect
import os

def silent_generator(fnc):

	@functools.wraps(fnc)
	async def wrapped(*args):
		await fnc(*args)
		yield None

	return wrapped

#-------------------------------------------------------------------------------

def adapter(fnc, possibly_asynchronous=True):
	fnc_nParams = fnc.__code__.co_argcount
	fnc_localVars = fnc.__code__.co_varnames
	fnc_params = fnc_localVars[0:fnc_nParams]

	utilized_params = list()
	for param_name in fnc_params:
		utilized_params.append(param_name)

	if possibly_asynchronous:
		is_awaitable = inspect.iscoroutinefunction(fnc)

		async def wrapped_call(variables):
			selected_args = [ variables[param] for param in utilized_params ]
			if is_awaitable: return await fnc(*selected_args)
			else: return fnc(*selected_args)

	else:
		def wrapped_call(variables):
			selected_args = [ variables[param] for param in utilized_params ]
			return fnc(*selected_args)

	return wrapped_call

#-------------------------------------------------------------------------------

def remove_prefix(text, prefix):
	if text.startswith(prefix):
		return text[len(prefix):]

	return text

#-------------------------------------------------------------------------------

__all__ = [
	"adapter",
	"remove_prefix"
]

