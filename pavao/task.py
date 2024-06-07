
import asyncio
import inspect
from datetime import datetime, timezone

from .utils import adapter
from .exception import PavaoException
class TaskException(PavaoException):
	pass

class TaskProblem:
	NONE = 0
	IN_EXECUTION = 1
	NOT_IN_EXECUTION = 2
	NOT_FOUND = 3

#-------------------------------------------------------------------------------

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

#-------------------------------------------------------------------------------


class Task:
	def __init__(self, specs):
		processor = specs['processor']
		if not inspect.isasyncgenfunction(processor):
			raise TaskException("Not an async generator")

		self.package = specs.get('package')
		self.name = specs['name']

		self.enabled = False
		self.function = adapter(processor,
			possibly_asynchronous=False)

		self.ident = None
		self.execution = None
		self.current_output = list()

	#----------------------------------------------------------------------------

	async def register_self(self, connection):
		result = await connection.fetchrow(
			assert_task_exists,
			self.package,
			self.name)

		self.ident = result['id']
		if result['enabled']:
			await self.enable()

	#----------------------------------------------------------------------------

	async def enable(self): self.enabled = True
	async def disable(self): self.enabled = False

	#----------------------------------------------------------------------------

	def create_future(self, args):
		start = datetime.now(timezone.utc)
		self.current_output = list()

		broadcaster = args['broadcaster']
		db_pool = args['db_pool']

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


	def run(self, loop, args):
		self.cancel_if_executing()
		task_future = self.create_future(args)
		self.execution = loop.create_task(task_future())

