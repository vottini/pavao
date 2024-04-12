
import asyncio
from croniter import croniter
from datetime import datetime, timedelta, timezone

from .utils import adapter
from .logger import Logger

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

class TaskData:
	def __init__(self, specs, start_time):
		self.package = specs.get('package')
		self.name = specs.get('name')
		self.function = adapter(specs['processor'])
		self.schedule = specs['schedule']

		self.ident = None
		self.enabled = False
		self.execution = None

		self.iterator = croniter(self.schedule, start_time)
		self.next_execution = self.iterator.get_next(datetime)


	def create_future(self, db_pool, broadcaster):
		start = datetime.now(timezone.utc)

		args = {
			'db_pool': db_pool,
			'broadcasting': broadcaster
		}

		async def async_task():

			try:
				result = await self.function(args)
				success = True

			except asyncio.CancelledError as e:
				result = "Cancelled during execution"
				success = False

			except Exception as exception:
				result = exception
				success = False

			finally:
				self.execution = None
				end = datetime.now(timezone.utc)
				async with db_pool.connection() as connection:
					await connection.execute(insert_task_run,
						self.ident, success, str(result),
						start, end)

		return async_task


	def cancel_if_executing(self):
		if self.execution is not None:
			self.execution.cancel()
			self.execution = None


	def lateness(self):
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
		start = datetime.now()
		for file_path, spec in modules.items():

			try:
				taskData = TaskData(spec, start)
				tasks.append(taskData)

			except KeyError as e:
				msg = f"Incomplete spec in '{file_path}': missing field {e}"
				Logger.warning(msg)
				continue

		self.loaded_tasks = tasks
		self.executor = self.loop.create_task(self.execute_tasks())


	async def register_tasks(self):
		async with self.db_pool.connection() as connection:
			for task_data in self.loaded_tasks:
				result = await connection.fetchrow(
					assert_task_exists,
					task_data.package,
					task_data.name)

				task_data.ident = result['id']
				task_data.enabled = result['enabled']


	async def execute_tasks(self):
		await self.register_tasks()

		# this exists to avoid all tasks that
		# were scheduled to run after a computer
		# that has beed suspended comes back again
		# during the next execution wake up

		skippable_lateness = timedelta(
			minutes=1, seconds=30)

		while len(self.loaded_tasks) > 0:
			await wait_whole_minute()
			now = datetime.now()

			for task in self.loaded_tasks:
				while task.lateness() > skippable_lateness:
					task.step_schedule()

				if task.next_execution <= now:
					task.step_schedule()

					if task.enabled:
						task.execute(
							self.loop,
							self.db_pool,
							self.broadcaster)

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


	def run_task(self, taskId):
		for task_data in self.loaded_tasks:
			if task_data.ident == taskId:
				task_data.execute(
					self.loop,
					self.db_pool,
					self.broadcaster)

				return True

		return False

	#--------------------------------------------------------

	def stop(self):
		if self.executor is not None:
			self.executor.cancel()
			self.executor = None


