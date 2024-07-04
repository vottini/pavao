
import asyncio
import pavao

from admin.common import localizer
from admin.common import create_message_localizer
from admin.common import assert_admin_access

task_blueprint = """

	root {
		package: nullable string,
		name: string,
		schedule: string,
		enabled: bool,
		optional nextExecution: instant,
		running: bool
	}

"""

@pavao.generates_json(string_blueprint=task_blueprint)
async def process(request, response, path_variables, server):
	task_data = server.scheduler.get_task(path_variables['task'])
	localization_priority = request.parse_locale_priority()

	if task_data is None:
		message_localizer = create_message_localizer(request)
		message_localizer.assign_response_error(response, "TASK_NOT_FOUND")
		response.set_status(404)
		return None

	result = {
		'name': task_data.localized_name(localization_priority),
		'package': task_data.localized_package(localization_priority),
		'schedule': task_data.schedule,
		'enabled': task_data.enabled,
		'running': task_data.execution is not None
	}

	if task_data.enabled:
		result['nextExecution'] = task_data.next_execution

	return result


@assert_admin_access
async def pavao_endpoint():

	return {
		'method': 'GET',
		'path': '/admin/tasks/{task:int}',
		'package': localizer.map("PACKAGE"),
		'functionality': localizer.map("VIEW_TASK"),
		'processor': process
	}

