
import asyncio
import pavao

enable_task = """

	UPDATE pavao.task
		SET enabled = FALSE
		WHERE id = $1;

"""

from admin.common import localizer
from admin.common import create_message_localizer
from admin.common import assert_admin_access

async def process(request, response, path_variables, db_connection, server, broadcasting):
	task_data = server.scheduler.get_task(path_variables['task'])

	if task_data is None:
		message_localizer = create_message_localizer(request)
		message_localizer.assign_response_error(response, "TASK_NOT_FOUND")
		response.set_status(404)
		return None

	await task_data.disable(broadcasting)
	await db_connection.execute(enable_task, task_data.ident)


@assert_admin_access
def pavao_endpoint():

	return {
		'method': 'DELETE',
		'path': '/admin/tasks/{task:int}/enable',
		'package': localizer.map("PACKAGE"),
		'functionality': localizer.map("ENABLE_TASKS"),
		'processor': process
	}

