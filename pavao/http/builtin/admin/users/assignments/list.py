
import asyncio
import pavao

from admin.common import localize_functionality

list_assignments = """

	SELECT rl.id, rl.name FROM pavao.assignment assign 
		INNER JOIN pavao.account acc ON assign.account = acc.id
		INNER JOIN pavao."role" rl ON assign."role" = rl.id
		WHERE NOT rl.admin AND acc.id = $1;

"""

assignments_blueprint = """

	root {
		id: integer,
		name: string
	} []

"""

@pavao.generatesJson(stringBlueprint=assignments_blueprint)
async def process(request, response, db_connection, path_variables):
	userId = path_variables['user']

	result = list()
	for classId, className in await db_connection.fetch(list_assignments, userId):
		entry = {'id': classId, 'name': className}
		result.append(entry)

	return result


async def pavao_endpoint(db_connection, parameters):
	package_name, func_name = await localize_functionality("LIST_ASSIGNMENTS",
		db_connection, parameters)

	return {
		'method': 'GET',
		'path': '/admin/assignments/{user:int}',
		'package': package_name,
		'functionality': func_name,
		'processor': process
	}

