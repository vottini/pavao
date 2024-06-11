
import asyncio
import pavao

from admin.common import localize_functionality
from admin.common import create_message_localizer

@pavao.generates_json(string_blueprint="root string[]")
async def process(request, response, path_variables, server):
	task_data = server.scheduler.get_task(path_variables['task'])
	localizer = create_message_localizer(request)

	if task_data is None:
		response.set_status(404)
		return localizer.create_error(
			"TASK_NOT_FOUND"
		)

	if task_data.execution is None: return list()
	return task_data.get_output()


async def pavao_endpoint(db_connection, persisted_settings):
	package_name, func_name = await localize_functionality("MONITOR_TASKS",
		db_connection, persisted_settings)

	return {
		'method': 'GET',
		'path': '/admin/tasks/{task:int}/output',
		'package': package_name,
		'functionality': func_name,
		'processor': process
	}

