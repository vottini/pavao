
import asyncio
import pavao

from admin.common import localizer
from admin.common import create_message_localizer
from admin.common import assert_admin_access

def process(request, response, path_variables, server):
	success, outcome = server.scheduler.run_task(path_variables['task'])
	if success: return

	status, msg = 500, "UNEXPECTED_ERROR"
	if outcome == pavao.TaskProblem.NOT_FOUND:
		msg = "TASK_NOT_FOUND"
		status = 404

	if outcome == pavao.TaskProblem.IN_EXECUTION:
		msg = "TASK_IN_EXECUTION"
		status = 409

	message_localizer = create_message_localizer(request)
	message_localizer.assign_response_error(response, msg)
	response.set_status(status)


@assert_admin_access
def pavao_endpoint():

	return {
		'method': 'POST',
		'path': '/admin/tasks/{task:int}/run',
		'package': localizer.map("PACKAGE"),
		'functionality': localizer.map("RUN_TASKS"),
		'processor': process
	}

