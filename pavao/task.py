
import asyncio
import inspect
from datetime import datetime, timezone

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

insert_task_output = """

	INSERT INTO pavao.task_output (task, instant, content)
	VALUES ($1, $2, $3);

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
		processor = specs['processor']
		if not inspect.isasyncgenfunction(processor):
			raise TaskException("Not an async generator")

		self.source = source
		self.package = specs.get('package')
		self.name = specs['name']

		self.enabled = True
		self.function = adapter(processor,
			possibly_asynchronous=False)

		self.ident = Task.generate_ident()
		self.execution = None

	#----------------------------------------------------------------------------

	async def register_self(self, connection):
		result = await connection.fetchrow(assert_task_exists,
			get_identity(self.package),
			get_identity(self.name))

		self.ident = result['id']
		if not result['enabled']:
			await self.disable()

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

	def create_future(self, args, on_output, on_finish):
		broadcaster = args['broadcasting']
		#db_pool = args['db_pool']

		async def process_output(output):
			await on_output(self, output)

			#if db_pool.configured:
			#	async with db_pool.connection() as connection:
			#		await connection.execute(insert_task_output, self.ident,
			#			datetime.now(timezone.utc), str(output))

		async def async_task():
			await broadcaster.write_message(
				f"taskState:{self.ident}",
				"STARTED"
			)

			try:
				async for output in self.function(args):
					if output is not None:
						await process_output(output)
						await broadcaster.write_message(
							f"taskState:{self.ident}",
							f'OUTPUT:{output}'
						)

				success = True

			except asyncio.CancelledError:
				output = "Cancelled during execution"
				await process_output(output)
				success = False

			except Exception as exception:
				output = str(exception)
				await process_output(output)
				success = False

			finally:
				self.execution = None
				await broadcaster.write_message(
					f"taskState:{self.ident}",
					"FINISHED"
				)

				if on_finish is not None:
					await on_finish(self.ident,
						success)

		return async_task


	def cancel_if_executing(self):
		if self.execution is None:
			return False

		self.execution.cancel()
		self.execution = None
		return True


	def run(self, loop, args, on_output, on_finish=None):
		self.cancel_if_executing()
		task_future = self.create_future(args, on_output, on_finish)
		self.execution = loop.create_task(task_future())

#-------------------------------------------------------------------------------

class TaskManager:
	def __init__(self, loop, server):
		self.loop = loop
		self.server = server
		#self.db_pool = server.db_pool
		self.broadcaster = server.broadcaster

		self.executor = None
		self.loaded_tasks = list()
		self.ctor = Task


	#--------------------------------------------------------

	async def execute_tasks(self):
		...

	#--------------------------------------------------------

	def parse_tasks(self, modules):
		tasks = list()

		for file_path, spec in modules.items():

			try:
				taskData = self.ctor(file_path, spec)
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

		async def execution():
			await self.register_tasks()
			await self.execute_tasks()

		self.executor = self.loop.create_task(execution())


	async def register_tasks(self):
		#if self.db_pool.configured:
		#	async with self.db_pool.connection() as connection:
		#		for task in self.loaded_tasks:
		#			await task.register_self(connection)
		pass

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
#
