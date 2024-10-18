
import asyncio

from .utils import adapter
from .task import Task, TaskManager
from .logger import Logger

class Daemon(TaskManager):
	def __init__(self, loop, server):
		TaskManager.__init__(self, loop, server)


	def start_task(self, task):
		finish_callbacks = list()
		def add_finish_callback(callback):
			finish_callbacks.append(callback)

		args = {
			'server': self.server,
			#'db_pool': self.db_pool,
			'broadcasting': self.broadcaster,
			'on_finish': add_finish_callback
		}

		async def on_finish(ident, success):
			for cb in finish_callbacks:
				adapted_cb = adapter(cb)
				await adapted_cb(dict())

		async def on_output(task, output): pass
		task.run(self.loop, args, on_output, on_finish)


	async def execute_tasks(self):
		for task in self.loaded_tasks:
			if task.enabled: self.start_task(task)

	#------------------------------------------------------------

	def stop_module(self, source):
		if (found := self.task_from_source(source)) is not None:
			found.cancel_if_executing()


	async def stop(self):
		for task in self.loaded_tasks:
			if task.execution is not None:
				task.execution.cancel()
				await task.execution

		self.executor.cancel()
		await self.executor
		self.executor = None

