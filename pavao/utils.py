
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

#-------------------------------------------------------------------------------

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


def async_adapter(fnc):
	asynchronous = inspect.iscoroutinefunction(fnc)
	if asynchronous:
		return fnc

	async def adaptation(*args): return fnc(*args)
	return adaptation

#-------------------------------------------------------------------------------

silent_generator_template = """

@functools.wraps(fnc)
async def wrapped({ALL_PARAMS}):
	all_args = {{ {CONTEXT} }}

	selected_args = list()
	for param_name in {FNC_PARAMS}:
		selected_args.append(all_args[param_name])

	await fnc(*selected_args)
	yield None

"""

def silent_generator(fnc):
	fnc_params = deduce_parameters(fnc)
	code = silent_generator_template.format(
		ALL_PARAMS=",".join(fnc_params),
		CONTEXT=",".join(map(lambda x : f"'{x}': {x}", fnc_params)),
		FNC_PARAMS=str(fnc_params)
	)

	namespace = globals().copy()
	scope = locals().copy()

	namespace.update({'fnc': fnc})
	exec(code, namespace, scope)
	return scope['wrapped']

#-------------------------------------------------------------------------------

def remove_prefix(text, prefix):
	if text.startswith(prefix):
		return text[len(prefix):]

	return text

#-------------------------------------------------------------------------------

class WrappedFunction:
	def __init__(self, preprocessor, processor, postprocessor):
		self.preprocessor = preprocessor
		self.processor = processor
		self.postprocessor = postprocessor

	async def __call__(self, context):
		if self.preprocessor is None:
			return await self.processor(context)

		try:
			await self.preprocessor(context)
			return await self.processor(context)

		finally:
			if self.postprocessor is not None:
				await self.postprocessor(context)

#-------------------------------------------------------------------------------

__all__ = [
	"deduce_parameters",
	"adapter",
	"async_adapter",
	"silent_generator",
	"remove_prefix",
	"WrappedFunction"
]

