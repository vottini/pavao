
from .logger import Logger

class RequestFilter:

	# for some reason, __subclasses__()
	# was returning only one filter when
	# using dynamic loading (importlib)

	implementations = list()
	def __init_subclass__(cls, **kwargs):
		super().__init_subclass__(**kwargs)
		RequestFilter.implementations.append(cls)

	async def init(self, loaded_settings): pass
	def enabled(self, endpoint_specs): return False
	async def allow(self): return True

#-------------------------------------------------------------------------------

def create_specs(filter_instance):
	return (filter_instance.enabled, filter_instance.allow)


class FilterCollection:
	def __init__(self):
		self.ordered_config = list()
		self.ordered_instances = list()
		self.unordered = list()


	async def init(self,
		loaded_settings,
		parameter_factory):

		found_filters = [
			(cls.__name__, cls())
			for cls in RequestFilter.implementations
		]

		collected_filters = dict()
		for name, instance in found_filters:
			await instance.init(loaded_settings)
			disabled_dep = parameter_factory.find_disabled_parameters(
				instance.allow)

			if disabled_dep is not None:
				Logger.warning(f"Filter '{name}' disabled due to missing dep '{disabled_dep}'")
				continue

			collected_filters[name] = instance
			Logger.info(f"Filter '{name}' loaded")

		for cls in self.ordered_config:
			if cls in collected_filters:
				instance = collected_filters.pop(cls)
				filter_specs = create_specs(instance)
				self.ordered_instances.append(instance)

		self.unordered = [
			create_specs(remaining_filter)
			for remaining_filter in collected_filters.values()
		]


	def list_filters(self):

		return (
			*self.ordered_instances,
			*self.unordered
		)

