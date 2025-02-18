
import asyncio
import inspect

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

insert_if_inexistent = """

	INSERT INTO task (package, name, enabled)
		SELECT :package, :name, TRUE
			WHERE NOT EXISTS (
				SELECT 1 FROM task
					WHERE
						package = :package AND
						"name" = :name
				)

"""

retrieve_task = """

	SELECT id, enabled FROM task
		WHERE
			package = :package AND
			"name" = :name

"""

insert_task_run = """

	INSERT INTO task_execution (task, execution_start)
		VALUES (:task, :start)
		RETURNING id;

"""

mark_execution_finish = """

	UPDATE task_execution SET
		execution_end = :end,
		success = :success

	WHERE id = :execution;

"""

insert_task_output = """

	INSERT INTO task_output (
		execution,
		instant,
		error,
		content
	)

	VALUES (
		:execution,
		:instant,
		:error,
		:content
	);

"""

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
			await_if_async=False)

		self.source = source
		self.package = specs.get('package')
		self.name = specs['name']

		self.enabled = True
		self.ident = Task.generate_ident()
		self.execution = None

	#----------------------------------------------------------------------------

	async def register_self(self, internal_db):

		args = {
			'package': get_identity(self.package),
			'name': get_identity(self.name)
		}

		async with internal_db.cursor() as cursor:
			await cursor.execute(insert_if_inexistent, args)
			retrieved = await cursor.execute(retrieve_task, args)
			self.ident, enabled = await retrieved.fetchone()

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
		broadcaster, internal_db, context,
		on_output, on_finish):

		async def async_task():
			start = datetime.now(timezone.utc)
			await broadcaster.write_message(
				f"taskState:{self.ident}",
				"STARTED"
			)

			async with internal_db.cursor() as cursor:
				await cursor.execute(insert_task_run, {
					'task': self.ident,
					'start': start
				})

				inserted_row = await cursor.fetchone()
				run_ident = inserted_row[0]
				await internal_db.commit()

			async def process_output(output, error):
				instant = datetime.now(timezone.utc)
				await on_output(self, output)

				async with internal_db.cursor() as cursor:
					await cursor.execute(insert_task_output, {
						'execution': run_ident,
						'instant': instant,
						'error': error,
						'content': str(output)
					})

				await internal_db.commit()

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

				self.execution = None
				await broadcaster.write_message(
					f"taskState:{self.ident}",
					"FINISHED"
				)

				if on_finish is not None:
					await on_finish(self.ident,
						run_ident,
						success)

				async with internal_db.cursor() as cursor:
					await cursor.execute(mark_execution_finish, {
						'execution': run_ident,
						'success': success,
						'end': end
					})

				await internal_db.commit()

		return async_task


	def cancel_if_executing(self):
		if self.execution is None:
			return False

		self.execution.cancel()
		self.execution = None
		return True


	def run(self, loop,
		broadcaster, internal_db, context,
		on_output, on_finish=None):

		self.cancel_if_executing()
		task_future = self.create_future(
			broadcaster, internal_db, context,
			on_output, on_finish)

		self.execution = loop.create_task(task_future())

#-------------------------------------------------------------------------------

class TaskManager:
	def __init__(self, loop, broadcaster):
		self.broadcaster = broadcaster
		self.loop = loop

		self.executor = None
		self.internal_db = None
		self.loaded_tasks = list()
		self.ctor = Task


	#--------------------------------------------------------

	async def execute_tasks(self): ...
	async def stop(self): ...

	def get_base_context(self):
		return set()

	#--------------------------------------------------------

	async def set_tasks(self, tasks, internal_db):
		await self.stop()

		self.internal_db = internal_db
		self.loaded_tasks = tasks

		async def execution():
			for task in self.loaded_tasks:
				await task.register_self(internal_db)

			await internal_db.commit()
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

