
import asyncio
import functools
import inspect
import os
import jsonbp

error_contents = '''

	root {
		error: String,
		description: String,
		timestamp: Instant
	}

'''

error_blueprint = jsonbp.load_string(error_contents)

#-------------------------------------------------------------------------------

def deduce_parameters(fnc):
	n_params = fnc.__code__.co_argcount
	variables = fnc.__code__.co_varnames
	is_bound = hasattr(fnc, '__self__')
	start_index = 1 if is_bound else 0
	return variables[start_index:n_params]

#-------------------------------------------------------------------------------

def adapter(fnc, wrap_as_coroutine=True):
	asynchronous = inspect.iscoroutinefunction(fnc)
	fnc_params = deduce_parameters(fnc)

	if wrap_as_coroutine and asynchronous:
		async def wrapped_call(variables):
			selected_args = [ variables[param] for param in fnc_params ]
			return await fnc(*selected_args)

	else:
		def wrapped_call(variables):
			selected_args = [ variables[param] for param in fnc_params ]
			return fnc(*selected_args)

	return wrapped_call


def async_adapter(fnc):
	if inspect.iscoroutinefunction(fnc):
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

	# exec is intentional: the DI system discovers injectable parameters by
	# reading co_varnames directly off the function object. A standard closure
	# or functools.wraps wrapper would expose the wrapper's own signature, not
	# the original function's parameters. exec generates a function whose
	# co_varnames exactly match fnc_params, preserving DI introspection through
	# arbitrarily deep decorator chains.
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
	"WrappedFunction",
	"error_contents",
	"error_blueprint"
]

