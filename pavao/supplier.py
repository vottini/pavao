
from .exception import PavaoException
class ParameterException(PavaoException):
	pass

from .logger import Logger
from .utils import deduce_parameters, async_adapter, adapter

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


	async def init(self, loaded_settings, verbose=False):

		# find and configure suppliers,
		# capture parameters and check for
		# ambiguity of suppliers

		impls = ParameterSupplier.implementations
		for supplier, name in ((cls(), cls.__name__) for cls in impls):
			supplier.configure(loaded_settings)

			supplied = supplier.parameters_supplied()
			if len(supplied) == 0:
				Logger.info(f"Supplier '{name}' found but supplies no parameters")
				continue

			self.suppliers.append(supplier)
			for parameter, methods in supplied.items():
				if parameter in self.parameters or parameter in self.base_parameters:
					msg = f"Multiple suppliers defined for parameter '{parameter}'"
					raise ParameterException(msg)

				self.parameters[parameter] = methods

			supplied_lst = ", ".join(supplied.keys())
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

		init_deps = {}
		for supplier in self.suppliers:
			dependencies = deduce_parameters(supplier.initialize)
			init_deps[supplier] = dependencies

			for parameter in dependencies:
				if not parameter in self.parameters:
					class_name = supplier.__class__.__name__
					msg = f"Unknown parameter '{parameter}' to initialize '{class_name}'"
					raise ParameterException(msg)

		param_to_supplier = {
			param: supplier
			for supplier in self.suppliers
			for param in supplier.parameters_supplied()
		}

		supplier_prereqs = {
			supplier: {
				param_to_supplier[dep]
				for dep in init_deps[supplier]
				if dep in param_to_supplier
			}
			for supplier in self.suppliers
		}

		in_path, visited, init_order = set(), set(), []

		def visit_supplier(supplier):
			if supplier in in_path:
				names = [s.__class__.__name__ for s in in_path]
				raise ParameterException(
					f"Circular initialization dependency among suppliers: {names}")
			if supplier in visited:
				return
			in_path.add(supplier)
			for prereq in supplier_prereqs[supplier]:
				visit_supplier(prereq)
			in_path.discard(supplier)
			visited.add(supplier)
			init_order.append(supplier)

		for supplier in self.suppliers:
			visit_supplier(supplier)

		for supplier in init_order:
			initializer = supplier.initialize
			dependencies = deduce_parameters(initializer)
			context = dict()

			for parameter in dependencies:
				await self.produce(
					parameter,
					context)

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

		for dep in generated_dependencies:
			if not dep in self.dependencies:
				msg = f"Parameter '{dep}' is neither baseline nor supplied"
				raise ParameterException(msg)

		generation_order = []
		visited = set(self.base_parameters)

		def visit(param):
			if param in visited:
				return
			visited.add(param)
			for dep in self.dependencies[param]:
				visit(dep)
			generation_order.append(param)

		for dep in generated_dependencies:
			visit(dep)

		if len(generation_order) > 0:
			reversed_generation = reversed(generation_order)
			destruction_order = tuple(reversed_generation)

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
		context = context if context is not None else dict()

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


	def unknown_deps(self, fnc):
		for parameter in deduce_parameters(fnc):
			if not parameter in { *self.parameters, *self.base_parameters }:
				return parameter


	def change_base(self, base_parameters):
		result = ParameterFactory(base_parameters)

		result.suppliers = self.suppliers
		result.parameters = self.parameters
		result.dependencies = self.dependencies
		return result

