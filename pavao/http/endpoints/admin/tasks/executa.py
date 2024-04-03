
import asyncio
import pavao

from admin.common import localize_functionality
from admin.common import create_message_localizer


def process(request, response, path_variables, server):
	success = server.scheduler.run_task(path_variables['task'])

	if not success:
		localizer = create_message_localizer(request)
		localizer.assign_response_error(response, "TASK_NOT_FOUND")
		response.set_status(404)
		return None

	response.set_status(204)


async def pavao_endpoint(db_connection, persisted_settings):
	package_name, func_name = await localize_functionality("RUN_TASKS",
		db_connection, persisted_settings)

	return {
		'method': 'POST',
		'path': '/admin/tasks/{task:int}/run',
		'package': package_name,
		'functionality': func_name,
		'processor': process
	}

