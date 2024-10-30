
import os
import asyncio

from .logger import Logger
from .exception import PavaoException
from .supplier import ParameterSupplier
from .utils import deduce_parameters
from .loader import load_folder


base_parameters = {
	'request',
	'response',
	'path_variables',
	'broadcasting',
	'receive'
}


class ParameterFactory:
	def __init__(self):
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

		for supplier in (cls() for cls in ParameterSupplier.implementations):
			await supplier.init(loaded_settings)
			self.suppliers.append(supplier)

			supplied = supplier.parameters_supplied()
			for parameter, methods in supplied.items():
				if parameter in self.parameters:
					msg = f"More than one supplier defined for parameter '{parameter}'"
					raise PavaoException(msg)

				self.parameters[parameter] = methods

		for parameter, (ctor, dtor) in self.parameters.items():
			dependencies = deduce_parameters(ctor)
			self.dependencies[parameter] = dependencies

			for dependency in dependencies:
				if not (dependency in self.parameters or dependency in base_parameters):
					msg = f"Unknown dependency '{dependency}' to produce '{parameter}'"
					raise PavaoException(msg)

		for parameter in self.parameters:
			self._check_circularity(parameter, set(), set())


	def _check_circularity(self, parameter, analyzed, produced):
		deps = self.dependencies[parameter]
		analyzed.add(parameter)

		for dependency in deps:
			if not dependency in produced:
				if dependency in analyzed:
					msg = f"Circular dependency on '{parameter}' to produce '{dependency}'"
					raise PavaoException(msg)

				self._check_circularity(dependency,
					analyzed, produced)

		produced.add(parameter)


	def create_wrappers(self, fnc):
		dependencies = deduce_parameters(fnc)
		generated_dependencies = set(dependencies) - base_parameters
		simple_deps = set()

		for dep in generated_dependencies:
			build_deps = self.dependencies[dep]
			if len(build_deps) == 0:
				simple_deps.add(dep)

		available_parameters = base_parameters | simple_deps
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
				raise PavaoException(msg)

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
							context[parameter])

			return (
				creation,
				tear_down
			)

		return None, None


	async def produce(self, parameter, context=None):
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
		ctor, dtor = self.parameters[parameter]
		if dtor is not None:
			await dtor(value)


	async def shutdown(self):
		for supplier in self.suppliers:
			await supplier.shutdown()

