
import asyncio
import pavao

from admin.common import localize_functionality
from admin.common import create_message_localizer


def process(request, response, path_variables, server):
	success, outcome = server.scheduler.run_task(path_variables['task'])

	if success:
		response.set_status(204)
		return

	localizer = create_message_localizer(request)
	msg = "UNEXPECTED_ERROR"
	status = 500

	if outcome == pavao.TaskProblem.NOT_FOUND:
		msg = "TASK_NOT_FOUND"
		status = 404

	if outcome == pavao.TaskProblem.IN_EXECUTION:
		msg = "TASK_IN_EXECUTION"
		status = 409

	localizer.assign_response_error(response, msg)
	response.set_status(status)


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

