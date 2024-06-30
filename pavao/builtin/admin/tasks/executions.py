
import re
import datetime
import asyncio
import pavao

from admin.common import localizer
from admin.common import create_message_localizer
from admin.common import assert_admin_access

select_executions = """

	SELECT
		id,
 		success,
		execution_start AS "start",
		execution_end AS "finish"

	FROM pavao.task_execution

	WHERE
		DATE(execution_start) = $2 AND
		execution_end IS NOT NULL AND
		task = $1;

"""

retrieve_outputs = """

	SELECT instant, content
		FROM pavao.task_output

		WHERE
			task = $1 AND
			instant > $2 AND
			instant < $3;

"""

executions_blueprint = """

	root {
		start: instant,
		finish: instant,
		success: bool,

		outputs: {
			instant: instant(iso=true),
			content: string
		} []
	} []

"""

day_pattern = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")

#-------------------------------------------------------------------------------

def make_datetime(day_str):
	return datetime.datetime.strptime(
		day_str, "%Y-%m-%d")


@pavao.generates_json(string_blueprint=executions_blueprint)
@pavao.accepts_parameters({'day': str})
async def process(request, response, parameters, db_connection, path_variables):
	day = parameters['day']

	if day_pattern.match(day) is None:
		response.set_status(400)
		message_localizer = create_message_localizer(request)
		return message_localizer.create_error(
			"INVALID_DAY"
		)

	task_id = path_variables['task']
	found = await db_connection.fetch(
		select_executions, task_id,
		make_datetime(day))

	outputs = dict()
	for execution in found:
		ident = execution['id']

		outputs[ident] = await db_connection.fetch(
			retrieve_outputs, task_id,
			execution['start'],
			execution['finish']
		)

	return [
		pavao.assemble_dicts(execution,
			outputs=[pavao.assemble_dicts(output)
				for output in outputs.get(execution['id'], list())
			]
		)

		for execution in found
	]


@assert_admin_access
def pavao_endpoint():

	return {
		'method': 'GET',
		'path': '/admin/tasks/{task:int}/executions',
		'package': localizer.map("PACKAGE"),
		'functionality': localizer.map("MONITOR_TASKS"),
		'processor': process,
		'public': True
	}


