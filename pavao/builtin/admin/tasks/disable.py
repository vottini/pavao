
import asyncio
import pavao

enable_task = """

	UPDATE pavao.task
		SET enabled = FALSE
		WHERE id = $1;

"""

from admin.common import localize_functionality
from admin.common import create_message_localizer

async def process(request, response, path_variables, db_connection, server, broadcasting):
	task_data = server.scheduler.get_task(path_variables['task'])

	if task_data is None:
		localizer = create_message_localizer(request)
		localizer.assign_response_error(response, "TASK_NOT_FOUND")
		response.set_status(404)
		return None

	await task_data.disable(broadcasting)
	await db_connection.execute(enable_task, task_data.ident)
	response.set_status(204)


async def pavao_endpoint(db_connection, persisted_settings):
	package_name, func_name = await localize_functionality("ENABLE_TASKS",
		db_connection, persisted_settings)

	return {
		'method': 'DELETE',
		'path': '/admin/tasks/{task:int}/enable',
		'package': package_name,
		'functionality': func_name,
		'processor': process
	}

