
class ParameterSupplier:

	# for some reason, __subclasses__()
	# was returning only one supplier when
	# using dynamic loading (importlib)

	implementations = list()
	def __init_subclass__(cls, **kwargs):
		super().__init_subclass__(**kwargs)
		ParameterSupplier.implementations.append(cls)

	def parameters_supplied(self): pass
	async def init(self, loaded_settings): pass
	async def shutdown(self): pass

