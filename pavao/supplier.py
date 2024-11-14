
import os
import asyncio

from .exception import PavaoException
class ParameterException(PavaoException):
	pass

from .logger import Logger
from .utils import deduce_parameters, async_adapter, adapter
from .loader import load_folder

#------------------------------------------------------------------------------

class ParameterSupplier:

	# for some reason, __subclasses__()
	# was returning only one supplier when
	# using dynamic loading (importlib)

	implementations = list()
	def __init_subclass__(cls, **kwargs):
		super().__init_subclass__(**kwargs)
		ParameterSupplier.implementations.append(cls)


	def configure(self, loaded_settings): pass
	def parameters_supplied(self): return dict()
	def initialize(self): pass
	def shutdown(self): pass

#------------------------------------------------------------------------------

class ParameterFactory:
	def __init__(self, base_parameters):
		self.base_parameters = base_parameters

		self.suppliers = list()
		self.parameters = dict()
		self.dependencies = dict()


	def _load_builtin_suppliers(self, verbose):
		Logger.info("Loading builtin suppliers...")
		basepath = os.path.dirname(os.path.realpath(__file__))
		suppliers_path = os.path.join(basepath, "suppliers")
		load_folder(suppliers_path, verbose)


	async def init(self, loaded_settings, verbose=False):
		self._load_builtin_suppliers(verbose)

		# find and configure suppliers,
		# capture parameters and check for
		# ambiguity of suppliers

		impls = ParameterSupplier.implementations
		for supplier, name in ((cls(), cls.__name__) for cls in impls):
			supplier.configure(loaded_settings)

			supplied = supplier.parameters_supplied()
			if len(supplied) == 0:
				continue

			self.suppliers.append(supplier)
			for parameter, methods in supplied.items():
				if parameter in self.parameters or parameter in self.base_parameters:
					msg = f"Multiple suppliers defined for parameter '{parameter}'"
					raise ParameterException(msg)

				self.parameters[parameter] = methods

			supplied_lst = ",".join(supplied.keys())
			Logger.info(f"Supplier '{name}' ({supplied_lst}) loaded")

		# scan each parameter's dependencies
		# and verify that they exist. After that,
		# check any dependency circularity

		for parameter, (ctor, dtor) in self.parameters.items():
			dependencies = deduce_parameters(ctor)
			self.dependencies[parameter] = dependencies

			for dependency in dependencies:
				if not (dependency in self.parameters or dependency in self.base_parameters):
					msg = f"Unknown parameter '{dependency}' to produce '{parameter}'"
					raise ParameterException(msg)

		for parameter in self.parameters:
			self._check_circularity(parameter, set(),
				set(self.base_parameters))

		# and finally setup each supplier,
		# producing all of its initialize dependencies

		#print("###", self.dependencies)

		for supplier in self.suppliers:
			#print("000", supplier.__class__.__name__)
			initializer = supplier.initialize
			dependencies = deduce_parameters(initializer)
			#print("111", dependencies)

			context = dict()
			for parameter in dependencies:
				if not dependency in self.parameters:
					class_name = supplier.__class__.__name__
					msg = f"Unknown parameter '{parameter}' to initialize '{class_name}'"
					raise ParameterException(msg)

				await self.produce(parameter, context)

			wrapped_initialize = async_adapter(adapter(initializer))
			await wrapped_initialize(context)

			for parameter in dependencies:
				await self.destroy(parameter,
					context[parameter])


	def _check_circularity(self, parameter, analyzed, produced):
		deps = self.dependencies[parameter]
		analyzed.add(parameter)

		for dependency in deps:
			if not dependency in produced:
				if dependency in analyzed:
					msg = f"Circular dependency on '{parameter}' to produce '{dependency}'"
					raise ParameterException(msg)

				self._check_circularity(dependency,
					analyzed, produced)

		produced.add(parameter)


	def create_wrappers(self, fnc):
		dependencies = deduce_parameters(fnc)
		generated_dependencies = set(dependencies) - self.base_parameters
		simple_deps = set()

		for dep in generated_dependencies:
			if not dep in self.dependencies:
				msg = f"Parameter '{dep}' is neither baseline nor supplied"
				raise ParameterException(msg)

			build_deps = self.dependencies[dep]
			if len(build_deps) == 0:
				simple_deps.add(dep)

		available_parameters = self.base_parameters | simple_deps
		remaining_deps = generated_dependencies - simple_deps
		generation_order = list(simple_deps)

		while len(remaining_deps) > 0:
			for parameter in remaining_deps:
				parameter_deps = self.dependencies[parameter]
				missing_deps = set(parameter_deps) - available_parameters

				if len(missing_deps) == 0:
					available_parameters.add(parameter)
					generation_order.append(parameter)
					remaining_deps.remove(parameter)
					break

			else:
				msg = f"Unable to create any of these parameters: {remaining_deps}"
				raise ParameterException(msg)

		if len(generation_order) > 0:
			destruction_order = reversed(generation_order)

			async def creation(context):
				for parameter in generation_order:
					if not parameter in context:
						await self.produce(parameter, context)

			async def tear_down(context):
				for parameter in destruction_order:
					if parameter in context:
						await self.destroy(parameter,
							context.pop(parameter))

			return (
				creation,
				tear_down
			)

		return None, None


	async def produce(self, parameter, context=None):
		if not parameter in self.parameters:
			msg = f"Unknown parameter '{parameter}'"
			raise ParameterException(msg)

		deps = self.dependencies[parameter]
		context = context or dict()

		for dependency in deps:
			if not dependency in context:
				await self.produce(dependency, context)

		arguments = list()
		for dependency in deps:
			arguments.append(context[dependency])

		ctor, dtor = self.parameters[parameter]
		result = await ctor(*arguments)
		context[parameter] = result
		return result


	async def destroy(self, parameter, value):
		ctor, dtor = self.parameters.get(parameter, (None,None))
		if dtor is not None:
			await dtor(value)


	async def shutdown(self):
		for supplier in self.suppliers:
			wrapped_shutdown = async_adapter(supplier.shutdown)
			await wrapped_shutdown()


	async def prepare_context(self, fnc, context=None):
		dependencies = deduce_parameters(fnc)
		context = context or dict()

		for parameter in dependencies:
			if parameter in context:
				continue

			if not parameter in self.parameters:
				msg = f"Unknown parameter '{parameter}'"
				raise ParameterException(msg)

			await self.produce(parameter, context)

		return context


	def has_unknown_parameters(self, fnc):
		for parameter in deduce_parameters(fnc):
			if not parameter in { *self.parameters, *self.base_parameters }:
				return parameter


	def change_base_parameters(self, base_parameters):
		result = ParameterFactory(base_parameters)

		result.suppliers = self.suppliers
		result.parameters = self.parameters
		result.dependencies = self.dependencies
		return result

