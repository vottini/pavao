
import asyncio
import pavao

from admin.common import localize_functionality
from admin.common import create_message_localizer

def process(request, response, path_variables, server):
	task_data = server.scheduler.get_task(path_variables['task'])
	localizer = create_message_localizer(request)

	if task_data is None:
		localizer.assign_response_error(response, "TASK_NOT_FOUND")
		response.set_status(404)
		return

	if not task_data.cancel_if_executing():
		localizer.assign_response_error(response, "TASK_IDLE")
		response.set_status(409)


async def pavao_endpoint(db_connection, persisted_settings):
	package_name, func_name = await localize_functionality("RUN_TASKS",
		db_connection, persisted_settings)

	return {
		'method': 'POST',
		'path': '/admin/tasks/{task:int}/stop',
		'package': package_name,
		'functionality': func_name,
		'processor': process
	}

