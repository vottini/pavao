
import asyncio
from croniter import croniter
from datetime import datetime, timedelta

from .logger import Logger
from .task import TaskException, TaskProblem, Task


class SchedulableTask(Task):
	def __init__(self, specs):
		Task.__init__(self, specs)
		self.schedule = specs['schedule']
		self.next_execution = None
		self.iterator = None


	def step_schedule(self):
		self.next_execution = self.iterator.get_next(datetime)


	def lateness(self):
		if not self.enabled:
			msg = "Task is not scheduled to be considered late"
			raise TaskException(msg)

		now = datetime.now()
		elapsed = now - self.next_execution
		return max(elapsed, timedelta())


	async def enable(self, broadcaster=None):
		self.iterator = croniter(self.schedule, datetime.now())
		self.next_execution = self.iterator.get_next(datetime)
		await Task.enable(self)

		if broadcaster is not None:
			await broadcaster.write_message(
				f"taskState:{self.ident}",
				f"ENABLED:{self.next_execution}"
			)


	async def disable(self, broadcaster=None):
		await Task.disable(self)
		self.next_execution = None
		self.iterator = None

		if broadcaster is not None:
			await broadcaster.write_message(
				f"taskState:{self.ident}",
				"DISABLED"
			)

#-------------------------------------------------------------------------------

async def wait_whole_minute():
	now = datetime.now()
	wait = (59-now.second) + (1000000-now.microsecond)/1e6
	await asyncio.sleep(wait)

	then = datetime.now()
	waited = then - now
	if waited > timedelta(minutes=2):
		await wait_whole_minute()

#-------------------------------------------------------------------------------

class Scheduler:
	def __init__(self, loop, server):
		self.loop = loop
		self.executor = None
		self.loaded_tasks = list()

		self.db_pool = server.db_pool
		self.broadcaster = server.broadcaster
		self.server = server


	def parse_tasks(self, modules):
		self.stop()

		tasks = list()
		for file_path, spec in modules.items():

			try:
				taskData = SchedulableTask(spec)
				tasks.append(taskData)

			except KeyError as e:
				msg = f"Incomplete spec in '{file_path}': missing field {e}"
				Logger.warning(msg)
				continue

			except TaskException as e:
				msg = f"Invalid task at '{file_path}': {e}"
				Logger.warning(msg)
				continue

		self.loaded_tasks = tasks
		self.executor = self.loop.create_task(self.execute_tasks())


	async def register_tasks(self):
		async with self.db_pool.connection() as connection:
			for task in self.loaded_tasks:
				await task.register_self(connection)


	async def execute_tasks(self):
		await self.register_tasks()

		# this exists to avoid all tasks that
		# were scheduled to run before a computer
		# has beed suspended to be executed when
		# it powers up again

		skippable_lateness = timedelta(
			minutes=1, seconds=30)

		while len(self.loaded_tasks) > 0:
			await wait_whole_minute()
			now = datetime.now()

			args = {
				'db_pool': self.db_pool,
				'broadcaster': self.broadcaster,
				'server': self.server
			}

			for task in self.loaded_tasks:
				if not task.enabled:
					continue

				if task.next_execution <= now:
					while task.lateness() > skippable_lateness:
						task.step_schedule()

					if task.next_execution <= now:
						task.run(self.loop, args)
						task.step_schedule()

					await self.broadcaster.write_message(
						f"taskState:{task.ident}",
						f'SCHEDULE:{task.next_execution}'
					)

	#--------------------------------------------------------

	def list_tasks(self):
		return [
			{
				'id': task_data.ident,
				'package': task_data.package,
				'name': task_data.name,
				'enabled': task_data.enabled
			}

			for task_data in self.loaded_tasks
		]


	def get_task(self, taskId):
		for task_data in self.loaded_tasks:
			if task_data.ident == taskId:
				return task_data

		return None

	#--------------------------------------------------------

	def _find_task(self, taskId):
		for task_data in self.loaded_tasks:
			if task_data.ident == taskId:
				return task_data

		return None


	def run_task(self, taskId):
		task_data = self._find_task(taskId)
		if task_data is None:
			return False, TaskProblem.NOT_FOUND

		if task_data.execution is not None:
			return False, TaskProblem.IN_EXECUTION

		args = {
			'db_pool': self.db_pool,
			'broadcaster': self.broadcaster,
			'server': self.server
		}

		task_data.run(self.loop, args)
		return True, TaskProblem.NONE


	def cancel_task(self, taskId):
		task_data = self._find_task(taskId)
		if task_data is None:
			return False, TaskProblem.NOT_FOUND

		if task_data.execution is None:
			return False, TaskProblem.NOT_IN_EXECUTION

		task_data.cancel_if_executing()
		return True, TaskProblem.NONE

	#--------------------------------------------------------

	def stop(self):
		if self.executor is not None:
			self.executor.cancel()
			self.executor = None


