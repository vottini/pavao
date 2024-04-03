
import asyncio
import pavao

task_blueprint = """

	root {
		schedule: string,
		package: nullable string,
		name: string,
		enabled: bool,
		nextExecution: instant
	}

"""

from admin.common import localize_functionality
from admin.common import create_message_localizer


@pavao.generates_json(string_blueprint=task_blueprint)
async def process(request, response, path_variables, server):
	task_data = server.scheduler.get_task(path_variables['task'])

	if task_data is None:
		localizer = create_message_localizer(request)
		localizer.assign_response_error(response, "TASK_NOT_FOUND")
		response.set_status(404)
		return None

	return {
		'name': task_data.name,
		'package': task_data.package,
		'schedule': task_data.schedule,
		'enabled': task_data.enabled,
		'nextExecution': task_data.next_execution
	}


async def pavao_endpoint(db_connection, persisted_settings):
	package_name, func_name = await localize_functionality("VIEW_TASK",
		db_connection, persisted_settings)

	return {
		'method': 'GET',
		'path': '/admin/tasks/{task:int}',
		'package': package_name,
		'functionality': func_name,
		'processor': process
	}

