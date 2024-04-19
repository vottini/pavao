
import re
import datetime
import asyncio
import pavao

from admin.common import localize_functionality
from admin.common import create_message_localizer

select_executions = """

	SELECT
  	success,
	  execution_start AS "start",
  	execution_end AS "finish",
	  "result" AS "outputs"

	FROM pavao.task_execution

	WHERE
		DATE(execution_start) = $2 AND
		task = $1;

"""

executions_blueprint = """

	root {
		start: instant,
		finish: nullable instant,
		success: bool,
		outputs: string[]
	} []

"""

day_pattern = re.compile(r"^20[0-9]{2}-[0-9]{2}-[0-9]{2}$")

#-------------------------------------------------------------------------------

def split_outputs(row):
	saned_row = row['outputs'] or ""
	return saned_row.split('\n')


def make_datetime(day_str):
	return datetime.datetime.strptime(
		day_str, "%Y-%m-%d")

#-------------------------------------------------------------------------------

@pavao.generates_json(string_blueprint=executions_blueprint)
@pavao.accepts_parameters({'day': str})
async def process(request, response, parameters, db_connection, path_variables):
	localizer = create_message_localizer(request)
	day = parameters['day']

	if day_pattern.match(day) is None:
		response.set_status(400)
		return localizer.create_error(
			"INVALID_DAY"
		)

	found = await db_connection.fetch(
		select_executions,
		path_variables['task'],
		make_datetime(day))

	return [
		pavao.assemble_dicts(row, outputs=split_outputs(row))
		for row in found
	]


async def pavao_endpoint(db_connection, persisted_settings):
	package_name, func_name = await localize_functionality("MONITOR_TASKS",
		db_connection, persisted_settings)

	return {
		'method': 'GET',
		'path': '/admin/tasks/{task:int}/executions',
		'package': package_name,
		'functionality': func_name,
		'processor': process,
		'public': True
	}


