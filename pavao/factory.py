
import os
import asyncio

from .logger import Logger
from .exception import PavaoException
from .supplier import ParameterSupplier
from .utils import deduce_parameters
from .loader import load_folder


basic_context = {
	'request',
	'response',
	'broadcasting',
	'server'
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
				if not (dependency in self.parameters or dependency in basic_context):
					msg = f"Unknown dependency '{dependency}' to produce '{parameter}'"
					raise PavaoException(msg)

		for parameter in self.parameters:
			self._check_circularity(parameter, set(), set())


	def _check_circularity(self, parameter, analyzed, produced):
		deps = self.dependencies[parameter]
		analyzed.add(parameter)

		for dep in deps:
			if not dep in produced:
				if dep in analyzed:
					msg = f"Circular dependency on '{parameter}' to produce '{dep}'"
					raise PavaoException(msg)

				self._check_circularity(dep, analyzed, produced)

		produced.add(parameter)


	def create_solution(self, fnc):
		pass


	async def produce(self, parameter, context=None):
		deps = self.dependencies[parameter]
		context = context or dict()

		for dep in deps:
			if not dep in context:
				self.produce(dep, context)

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

