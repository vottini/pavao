
import asyncio
from datetime import datetime
from datetime import timedelta

from .utils import adapter
from .task import Task, TaskManager
from .logger import Logger

class Daemon(TaskManager):
	def __init__(self, loop, broadcaster):
		TaskManager.__init__(self, loop, broadcaster)

		self.restating = None
		self.running_tasks = set()
		self.finished_tasks = dict()
		self.active = False


	def get_base_context(self):

		return {
			'broadcasting',
			'on_finish'
		}


	def start_task(self, task):
		finish_callbacks = list()
		def add_finish_callback(callback):
			finish_callbacks.append(callback)

		args = {
			'broadcasting': self.broadcaster,
			'on_finish': add_finish_callback
		}

		async def on_finish(ident, success):
			for cb in finish_callbacks:
				adapted_cb = adapter(cb)
				await adapted_cb(dict())

			self.finished_tasks[task.source] = datetime.now()

			if self.active:
				verbose = "success" if success else "error"
				Logger.info(f"Service from '{task.source}' finished with "
					+ verbose)

		async def on_output(task, output): pass
		task.run(self.loop, self.broadcaster, args,
			on_output, on_finish)


	async def execute_tasks(self):
		self.active = True

		for task in self.loaded_tasks:
			if task.enabled:
				Logger.info(f"Starting service from '{task.source}'")
				self.running_tasks.add(task.source)
				self.start_task(task)

		if len(self.running_tasks) > 0:
			self.restarting = self.loop.create_task(
				self.restart_services())


	async def restart_services(self):
		await asyncio.sleep(5)

		while self.active:
			now = datetime.now()
			retained = dict()

			for source, termination in self.finished_tasks.items():
				if source in self.running_tasks:
					if (now - termination) > timedelta(seconds=5):
						Logger.info(f"Restarting service from '{source}'")
						task = self.task_from_source(source)
						self.start_task(task)

					else:
						retained[source] = termination

			self.finished_tasks = retained
			await asyncio.sleep(5)

	#------------------------------------------------------------

	def stop_module(self, source):
		if (found := self.task_from_source(source)) is not None:
			self.running_tasks.remove(source)
			found.cancel_if_executing()


	def start_module(self, source):
		if not source in self.running_tasks:
			if (found := self.task_from_source(source)) is not None:
				self.running_tasks.add(source)
				self.start_task(found)


	async def stop(self):
		self.active = False

		if self.restating is not None:
			self.restating.cancel()
			self.restating = None

		if self.executor is not None:
			for task in self.loaded_tasks:
				if task.execution is not None:
					task.execution.cancel()
					await task.execution

			self.executor.cancel()
			await self.executor
			self.executor = None

		self.running_tasks = set()
		self.finished_tasks = dict()

