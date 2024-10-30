
import asyncio
import functools
import inspect
import os

#-------------------------------------------------------------------------------

def deduce_parameters(fnc):
	n_params = fnc.__code__.co_argcount
	variables = fnc.__code__.co_varnames
	bound_method = hasattr(fnc, '__self__')
	start_index = 1 if bound_method else 0
	return variables[start_index:n_params]


def adapter(fnc, possibly_asynchronous=True):
	fnc_params = deduce_parameters(fnc)

	utilized_params = list()
	for param_name in fnc_params:
		utilized_params.append(param_name)

	asynchronous = False
	if possibly_asynchronous:
		asynchronous = inspect.iscoroutinefunction(fnc)

	if asynchronous:
		async def wrapped_call(variables):
			selected_args = [ variables[param] for param in utilized_params ]
			return await fnc(*selected_args)

	else:
		def wrapped_call(variables):
			selected_args = [ variables[param] for param in utilized_params ]
			return fnc(*selected_args)

	return wrapped_call

#-------------------------------------------------------------------------------

def async_adapter(fnc):
	asynchronous = inspect.iscoroutinefunction(fnc)
	if asynchronous:
		return fnc

	async def adaptation(*args): return fnc(*args)
	return adaptation

#-------------------------------------------------------------------------------

def silent_generator(fnc):

	@functools.wraps(fnc)
	async def wrapped(*args):
		await fnc(*args)
		yield None

	return wrapped


def remove_prefix(text, prefix):
	if text.startswith(prefix):
		return text[len(prefix):]

	return text

#-------------------------------------------------------------------------------

__all__ = [
	"deduce_parameters",
	"adapter",
	"async_adapter",
	"silent_generator",
	"remove_prefix"
]

