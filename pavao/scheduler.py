
import asyncio
import inspect
from croniter import croniter
from datetime import datetime, timedelta, timezone

from .logger import Logger
from .utils import adapter
from .exception import PavaoException
class TaskException(PavaoException):
	pass

#-------------------------------------------------------------------------------

assert_task_exists = """

	WITH

	existing AS (
		SELECT id, enabled FROM pavao.task
		WHERE package = $1 AND "name" = $2
	),

	created AS (
		INSERT INTO pavao.task (package, name, enabled)
			SELECT $1, $2, TRUE
				WHERE NOT EXISTS (
					SELECT 1 FROM pavao.task
					WHERE package = $1 AND "name" = $2
				)

		RETURNING id, enabled
	)

	SELECT id, enabled FROM existing UNION ALL
	SELECT id, enabled FROM created;

"""


insert_task_run = """

	INSERT INTO pavao.task_execution (
		task,
		success,
		result,
		execution_start,
		execution_end
	)

	VALUES (
		$1,
		$2,
		$3,
		$4,
		$5
	);

"""

#-------------------------------------------------------------------------------

class TaskProblem:
	NONE = 0
	IN_EXECUTION = 1
	NOT_IN_EXECUTION = 2
	NOT_FOUND = 3


class TaskData:
	def __init__(self, specs):
		if not inspect.isasyncgenfunction(specs['processor']):
			raise TaskException("Not an async generator")

		self.package = specs.get('package')
		self.name = specs['name']

		self.schedule = specs['schedule']
		self.function = adapter(specs['processor'],
			possibly_asynchronous=False)

		self.ident = None
		self.execution = None
		self.current_output = list()

		self.enabled = False
		self.next_execution = None
		self.iterator = None

	#----------------------------------------------------------------------------

	async def enable(self, broadcaster=None):
		self.iterator = croniter(self.schedule, datetime.now())
		self.next_execution = self.iterator.get_next(datetime)
		self.enabled = True

		if broadcaster is not None:
			await broadcaster.write_message(
				f"taskState:{self.ident}",
				f"ENABLED:{self.next_execution}"
			)


	async def disable(self, broadcaster=None):
		self.enabled = False
		self.next_execution = None
		self.iterator = None

		if broadcaster is not None:
			await broadcaster.write_message(
				f"taskState:{self.ident}",
				"DISABLED"
			)

	#----------------------------------------------------------------------------

	def create_future(self, db_pool, broadcaster):
		start = datetime.now(timezone.utc)
		self.current_output = list()

		args = {
			'db_pool': db_pool,
			'broadcasting': broadcaster
		}

		async def async_task():
			await broadcaster.write_message(
				f"taskState:{self.ident}",
				"STARTED"
			)

			try:
				async for output in self.function(args):
					self.current_output.append(output)
					await broadcaster.write_message(
						f"taskState:{self.ident}",
						f'OUTPUT:{output}'
					)

				success = True

			except asyncio.CancelledError as e:
				self.current_output.append("Cancelled during execution")
				success = False

			except Exception as exception:
				self.current_output.append(str(exception))
				success = False

			finally:
				self.execution = None
				await broadcaster.write_message(
					f"taskState:{self.ident}",
					"FINISHED"
				)

				end = datetime.now(timezone.utc)
				result = "\n".join(self.current_output)
				async with db_pool.connection() as connection:
					await connection.execute(insert_task_run,
						self.ident, success, str(result),
						start, end)

		return async_task


	def cancel_if_executing(self):
		if self.execution is None:
			return False

		self.execution.cancel()
		self.execution = None
		return True


	def lateness(self):
		if not self.enabled:
			msg = "Task is not scheduled to be late"
			raise TaskException(msg)

		now = datetime.now()
		elapsed = now - self.next_execution
		return max(elapsed, timedelta())


	def step_schedule(self):
		self.next_execution = self.iterator.get_next(datetime)


	def execute(self, loop, db_pool, broadcaster):
		self.cancel_if_executing()
		task_future = self.create_future(db_pool, broadcaster)
		self.execution = loop.create_task(task_future())

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
	def __init__(self, loop, db_pool, broadcaster):
		self.loop = loop
		self.db_pool = db_pool
		self.broadcaster = broadcaster
		self.loaded_tasks = list()
		self.executor = None


	def parse_tasks(self, modules):
		self.stop()

		tasks = list()
		for file_path, spec in modules.items():

			try:
				taskData = TaskData(spec)
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
				result = await connection.fetchrow(
					assert_task_exists,
					task.package,
					task.name)

				task.ident = result['id']
				if result['enabled']:
					await task.enable()


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

			for task in self.loaded_tasks:
				if not task.enabled:
					continue

				if task.next_execution <= now:
					while task.lateness() > skippable_lateness:
						task.step_schedule()

					if task.next_execution <= now:
						task.execute(self.loop, self.db_pool, self.broadcaster)
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

		task_data.execute(
			self.loop,
			self.db_pool,
			self.broadcaster)

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


