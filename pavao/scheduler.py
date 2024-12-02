
import asyncio
from croniter import croniter
from datetime import datetime, timedelta, timezone
from .task import TaskException, TaskProblem, Task, TaskManager

class SchedulableTask(Task):
	def __init__(self, source, specs):
		Task.__init__(self, source, specs)

		self.schedule = specs['schedule']
		self.current_output = list()
		self.next_execution = None
		self.scheduler = None


	def step_schedule(self):
		self.next_execution = self.scheduler.get_next(datetime)


	def lateness(self):
		if not self.enabled:
			msg = "Task is not scheduled to be considered late"
			raise TaskException(msg)

		now = datetime.now()
		elapsed = now - self.next_execution
		return max(elapsed, timedelta())


	async def enable(self, broadcaster=None):
		self.scheduler = croniter(self.schedule, datetime.now())
		self.next_execution = self.scheduler.get_next(datetime)
		await Task.enable(self)

		if broadcaster is not None:
			await broadcaster.write_message(
				f"taskState:{self.ident}",
				f"ENABLED:{self.next_execution}"
			)


	async def disable(self, broadcaster=None):
		await Task.disable(self)
		self.next_execution = None
		self.scheduler = None

		if broadcaster is not None:
			await broadcaster.write_message(
				f"taskState:{self.ident}",
				"DISABLED"
			)


	def get_output(self): return self.current_output[:]
	def append_output(self, output): self.current_output.append(str(output))
	def clear_output(self): self.current_output = list()

#-------------------------------------------------------------------------------

insert_task_run = """

	INSERT INTO pavao.task_execution (
		task,
		success,
		execution_start,
		execution_end
	)

	VALUES (
		$1,
		$2,
		$3,
		$4
	);

"""


async def wait_whole_minute():
	start = datetime.now()
	wait = (59-start.second) + (1000000-start.microsecond)/1e6
	await asyncio.sleep(wait)

	end = datetime.now()
	waited = end - start
	if waited > timedelta(minutes=2):
		await wait_whole_minute()

#-------------------------------------------------------------------------------

class Scheduler(TaskManager):
	def __init__(self, loop, broadcaster):
		TaskManager.__init__(self, loop, broadcaster)
		self.ctor = SchedulableTask


	def get_base_context(self):
		return { 'broadcasting' }


	def start_task(self, task):
		start = datetime.now(timezone.utc)

		async def on_finish(task_ident, success):
			end = datetime.now(timezone.utc)
			task.clear_output()

			#async with self.db_pool.connection() as connection:
			#	await connection.execute(insert_task_run,
			#		task_ident, success, start, end)

		args = {
			'broadcasting': self.broadcaster
		}

		async def on_output(task, output):
			task.append_output(output)

		task.run(self.loop,
			self.broadcaster, args,
			on_output, on_finish)

	#--------------------------------------------------------

	def _verify_task(self, task, should_be_running):
		if task is None: return TaskProblem.NOT_FOUND

		if should_be_running:
			if task.execution is None:
				return TaskProblem.NOT_IN_EXECUTION

		if not should_be_running:
			if task.execution is not None:
				return TaskProblem.IN_EXECUTION

		return TaskProblem.NONE


	def run_task(self, taskId):
		task_data = self.get_task(taskId)
		problem = self._verify_task(task_data,
			should_be_running=False)

		if problem == TaskProblem.NONE:
			self.start_task(task_data)
			return True, TaskProblem.NONE

		return False, problem


	def cancel_task(self, taskId):
		task_data = self.get_task(taskId)
		problem = self._verify_task(task_data,
			should_be_running=True)

		if problem == TaskProblem.NONE:
			task_data.cancel_if_executing()
			return True, TaskProblem.NONE

		return False, problem

	#--------------------------------------------------------

	async def execute_tasks(self):

		# skippable_lateness exists solely to avoid all
		# tasks that were scheduled to run before a computer
		# has beed suspended to be executed at once
		# when the machine powers up again

		skippable_lateness = timedelta(
			minutes=1, seconds=30)

		while len(self.loaded_tasks) > 0:
			await wait_whole_minute()
			now = datetime.now()

			for task in self.loaded_tasks:
				if not task.enabled:
					continue

				if task.next_execution <= now:
					while task.lateness() > skippable_lateness:
						task.step_schedule()

					if task.next_execution <= now:
						self.start_task(task)
						task.step_schedule()

					await self.broadcaster.write_message(
						f"taskState:{task.ident}",
						f'SCHEDULE:{task.next_execution}'
					)

	#--------------------------------------------------------

	async def stop(self):
		if self.executor is not None:
			self.executor.cancel()
			self.executor = None

