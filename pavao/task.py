
import asyncio
import inspect
from abc import ABC, abstractmethod

from datetime import datetime
from datetime import timezone

from .logger import Logger
from .utils import adapter
from .i18n import LazyLocalizer

from .exception import PavaoException
class TaskException(PavaoException):
	pass

class TaskProblem:
	NONE = 0
	IN_EXECUTION = 1
	NOT_IN_EXECUTION = 2
	NOT_FOUND = 3

#-------------------------------------------------------------------------------

#-------------------------------------------------------------------------------

def get_identity(entity):
	return (entity.identity()
		if isinstance(entity, LazyLocalizer)
		else entity)

#-------------------------------------------------------------------------------

class Task:
	ident_counter = 1

	@staticmethod
	def generate_ident():
		ident = Task.ident_counter
		Task.ident_counter += 1
		return ident


	def __init__(self, source, specs):
		self.processor = specs['processor']
		if not inspect.isasyncgenfunction(self.processor):
			raise TaskException("'processor' is not an async generator")

		self.pre_processing = None
		self.post_processing = None
		self.function = adapter(self.processor,
			wrap_as_coroutine=False)

		self.source = source
		self.package = specs.get('package')
		self.name = specs['name']

		self.enabled = True
		self.ident = Task.generate_ident()
		self.execution = None

	#----------------------------------------------------------------------------

	async def register_self(self, task_store):
		self.ident, enabled = await task_store.register_task(
			get_identity(self.name),
			get_identity(self.package)
		)
		setup = self.enable if enabled else self.disable
		await setup()

	#----------------------------------------------------------------------------

	async def enable(self): self.enabled = True
	async def disable(self): self.enabled = False

	#----------------------------------------------------------------------------

	def localized_package(self, accepted_languages):
		return (self.package.localize(accepted_languages)
			if isinstance(self.package, LazyLocalizer)
			else self.package)


	def localized_name(self, accepted_languages):
		return (self.name.localize(accepted_languages)
			if isinstance(self.name, LazyLocalizer)
			else self.name)

	#----------------------------------------------------------------------------

	def create_future(self,
		broadcaster, task_store, context,
		on_output, on_finish):

		async def async_task():
			start = datetime.now(timezone.utc)
			await broadcaster.write_message(
				f"taskState:{self.ident}",
				"STARTED"
			)

			run_ident = await task_store.start_execution(self.ident, start)

			async def process_output(output, error):
				instant = datetime.now(timezone.utc)
				await on_output(self, output)
				await task_store.record_output(run_ident, instant, str(output), error)

			try:
				if self.pre_processing is not None:
					await self.pre_processing(context)

				async for output in self.function(context):
					if output is not None:
						await process_output(output, False)
						await broadcaster.write_message(
							f"taskState:{self.ident}",
							f'OUTPUT:{output}'
						)

				success = True

			except asyncio.CancelledError:
				output = "Cancelled during execution"
				await process_output(output, True)
				success = False

			except Exception as exception:
				output = str(exception)
				await process_output(output, True)
				success = False

			finally:
				end = datetime.now(timezone.utc)
				if self.post_processing is not None:
					await self.post_processing(context)

				if self.execution is asyncio.current_task():
					self.execution = None
				await broadcaster.write_message(
					f"taskState:{self.ident}",
					"FINISHED"
				)

				if on_finish is not None:
					await on_finish(self.ident, run_ident, success)

				await task_store.finish_execution(run_ident, end, success)

		return async_task


	def cancel_if_executing(self):
		if self.execution is None:
			return False

		self.execution.cancel()
		return True


	def run(self, loop,
		broadcaster, task_store, context,
		on_output, on_finish=None):

		self.cancel_if_executing()
		task_future = self.create_future(
			broadcaster, task_store, context,
			on_output, on_finish)

		self.execution = loop.create_task(task_future())

#-------------------------------------------------------------------------------

class TaskManager(ABC):
	def __init__(self, loop, broadcaster):
		self.broadcaster = broadcaster
		self.loop = loop

		self.executor = None
		self.task_store = None
		self.loaded_tasks = list()
		self.ctor = Task


	#--------------------------------------------------------

	@abstractmethod
	async def execute_tasks(self):
		...

	@abstractmethod
	async def stop(self):
		...

	def get_base_context(self):
		return set()

	#--------------------------------------------------------

	async def set_tasks(self, tasks, task_store):
		await self.stop()

		self.task_store = task_store
		self.loaded_tasks = tasks

		async def execution():
			for task in self.loaded_tasks:
				await task.register_self(task_store)

			await self.execute_tasks()

		self.executor = self.loop.create_task(execution())

	#----------------------------------------------------------------------------

	def list_tasks(self, localization_priority):

		return [
			{
				'id': task_data.ident,
				'package': task_data.localized_package(localization_priority),
				'name': task_data.localized_name(localization_priority),
				'enabled': task_data.enabled
			}

			for task_data in self.loaded_tasks
		]


	def get_task(self, taskId):
		for task_data in self.loaded_tasks:
			if task_data.ident == taskId:
				return task_data

		return None


	def task_from_source(self, source):
		for task_data in self.loaded_tasks:
			if task_data.source == source:
				return task_data

		return None

