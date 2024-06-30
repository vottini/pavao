
import asyncio
import pavao

from admin.common import localizer
from admin.common import create_message_localizer
from admin.common import assert_admin_access

def process(request, response, path_variables, server):
	task_data = server.scheduler.get_task(path_variables['task'])
	message_localizer = create_message_localizer(request)

	if task_data is None:
		message_localizer.assign_response_error(response, "TASK_NOT_FOUND")
		response.set_status(404)
		return

	if not task_data.cancel_if_executing():
		message_localizer.assign_response_error(response, "TASK_IDLE")
		response.set_status(409)


@assert_admin_access
def pavao_endpoint():

	return {
		'method': 'POST',
		'path': '/admin/tasks/{task:int}/stop',
		'package': localizer.map("PACKAGE"),
		'functionality': localizer.map("RUN_TASKS"),
		'processor': process
	}

