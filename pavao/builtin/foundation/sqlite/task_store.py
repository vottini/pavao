
from datetime import date, datetime
from typing import Optional

from pavao.persistence import TaskStore


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

set_task_enabled_query = """

	UPDATE task
		SET enabled = :enabled
		WHERE id = :task_id;

"""

list_tasks_query = """

	SELECT id, package, name, enabled FROM task;

"""

get_executions_query = """

	SELECT id, success, execution_start, execution_end
	FROM task_execution
	WHERE task = :task_id
		AND execution_end IS NOT NULL;

"""

get_executions_by_day_query = """

	SELECT id, success, execution_start, execution_end
	FROM task_execution
	WHERE task = :task_id
		AND DATE(execution_start) = :day
		AND execution_end IS NOT NULL;

"""

get_outputs_query = """

	SELECT instant, error, content
	FROM task_output
	WHERE execution = :execution_id
	ORDER BY instant;

"""

#-------------------------------------------------------------------------------

class SqliteTaskStore(TaskStore):

	def __init__(self, connection):
		self.connection = connection

	async def register_task(self,
		name: str,
		package: Optional[str]) -> tuple:

		args = {'package': package, 'name': name}
		async with self.connection.cursor() as cursor:
			await cursor.execute(insert_if_inexistent, args)
			retrieved = await cursor.execute(retrieve_task, args)
			task_id, enabled = await retrieved.fetchone()

		await self.connection.commit()
		return task_id, enabled

	async def start_execution(self,
		task_id: int,
		started_at: datetime) -> int:

		async with self.connection.cursor() as cursor:
			await cursor.execute(insert_task_run, {
				'task': task_id,
				'start': started_at
			})
			row = await cursor.fetchone()

		await self.connection.commit()
		return row[0]

	async def record_output(self,
		execution_id: int,
		instant: datetime,
		content: str,
		is_error: bool) -> None:

		async with self.connection.cursor() as cursor:
			await cursor.execute(insert_task_output, {
				'execution': execution_id,
				'instant': instant,
				'error': is_error,
				'content': content
			})

		await self.connection.commit()

	async def finish_execution(self,
		execution_id: int,
		ended_at: datetime,
		success: bool) -> None:

		async with self.connection.cursor() as cursor:
			await cursor.execute(mark_execution_finish, {
				'execution': execution_id,
				'success': success,
				'end': ended_at
			})

		await self.connection.commit()

	async def set_task_enabled(self,
		task_id: int,
		enabled: bool) -> None:

		async with self.connection.cursor() as cursor:
			await cursor.execute(set_task_enabled_query, {
				'task_id': task_id,
				'enabled': enabled
			})

		await self.connection.commit()


	async def list_tasks(self) -> list:
		async with self.connection.execute(list_tasks_query) as cursor:
			rows = await cursor.fetchall()

		return [
			{'id': id, 'package': package, 'name': name, 'enabled': enabled}
			for id, package, name, enabled in rows
		]

	async def get_executions(self,
		task_id: int,
		day: Optional[date] = None) -> list:

		if day is None:
			query, args = get_executions_query, {'task_id': task_id}
		else:
			query = get_executions_by_day_query
			args = {'task_id': task_id, 'day': day.isoformat()}

		async with self.connection.execute(query, args) as cursor:
			rows = await cursor.fetchall()

		return [
			{'id': id, 'success': success,
			 'execution_start': start, 'execution_end': end}
			for id, success, start, end in rows
		]

	async def get_outputs(self, execution_id: int) -> list:
		async with self.connection.execute(
			get_outputs_query, {'execution_id': execution_id}
		) as cursor:
			rows = await cursor.fetchall()

		return [
			{'instant': instant, 'error': error, 'content': content}
			for instant, error, content in rows
		]
