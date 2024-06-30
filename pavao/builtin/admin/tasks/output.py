
import asyncio
import pavao

from admin.common import localizer
from admin.common import create_message_localizer
from admin.common import assert_admin_access

@pavao.generates_json(string_blueprint="root string[]")
async def process(request, response, path_variables, server):
	task_data = server.scheduler.get_task(path_variables['task'])

	if task_data is None:
		response.set_status(404)
		message_localizer = create_message_localizer(request)
		return message_localizer.create_error(
			"TASK_NOT_FOUND"
		)

	if task_data.execution is None: return list()
	return task_data.get_output()


@assert_admin_access
def pavao_endpoint():

	return {
		'method': 'GET',
		'path': '/admin/tasks/{task:int}/output',
		'package': localizer.map("PACKAGE"),
		'functionality': localizer.map("MONITOR_TASKS"),
		'processor': process
	}


