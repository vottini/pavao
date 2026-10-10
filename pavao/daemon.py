
import asyncio
from datetime import datetime, timezone
from datetime import timedelta

from .utils import async_adapter
from .task import Task, TaskManager
from .logger import Logger

class Daemon(TaskManager):
	def __init__(self, loop, broadcaster):
		TaskManager.__init__(self, loop, broadcaster)

		self.restarter = None
		self.enabled_services = set()
		self.finished_services = dict()
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

		context = {
			'broadcasting': self.broadcaster,
			'on_finish': add_finish_callback
		}

		async def on_output(task, output):
			await self.broadcaster.write_message(
				f"taskState:{task.ident}",
				f"OUTPUT:{output}"
			)
		async def on_finish(task_ident, run_ident, success):
			for cb in finish_callbacks:
				adapted_cb = async_adapter(cb)
				await adapted_cb()

			self.finished_services[task.source] = datetime.now(timezone.utc)

			if self.active:
				Logger.info(f"Service from '{task.source}' terminated "
					+ ("cleanly" if success else "with error"))

		task.run(self.loop,
			self.broadcaster, self.task_store, context,
			on_output, on_finish)


	async def execute_tasks(self):
		self.active = True

		for task in self.loaded_tasks:
			if task.enabled:
				Logger.info(f"Starting service from '{task.source}'")
				self.enabled_services.add(task.source)
				self.start_task(task)

		if len(self.enabled_services) > 0:
			self.restarter = self.loop.create_task(
				self.restart_services())


	async def restart_services(self):
		await asyncio.sleep(5)

		while self.active:
			now = datetime.now(timezone.utc)
			retained = dict()

			for source, termination in self.finished_services.items():
				if source in self.enabled_services:
					if (now - termination) > timedelta(seconds=5):
						Logger.info(f"Restarting service from '{source}'")
						task = self.task_from_source(source)
						self.start_task(task)

					else:
						retained[source] = termination

			self.finished_services = retained
			await asyncio.sleep(5)

	#------------------------------------------------------------

	def stop_module(self, source):
		if (found := self.task_from_source(source)) is not None:
			self.enabled_services.remove(source)
			found.cancel_if_executing()


	def start_module(self, source):
		if not source in self.enabled_services:
			if (found := self.task_from_source(source)) is not None:
				self.enabled_services.add(source)
				self.start_task(found)


	async def stop(self):
		self.active = False

		if self.restarter is not None:
			self.restarter.cancel()
			self.restarter = None

		if self.executor is not None:
			for task in self.loaded_tasks:
				execution = task.execution
				if execution is not None:
					execution.cancel()
					await execution

			self.executor.cancel()
			await self.executor
			self.executor = None

		self.enabled_services = set()
		self.finished_services = dict()

