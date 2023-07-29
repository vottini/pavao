
import asyncio
import pavao

from access.registering import localize_functionality

find_user = "SELECT * FROM pavao.account WHERE id = $1"

list_assignments = """

	SELECT cls.id, cls.name FROM pavao.assignment assign 
		INNER JOIN pavao.account acc ON assign.account = acc.id
		INNER JOIN pavao.class cls ON assign.cls = cls.id
		WHERE cls.admin AND acc.id = $1;

"""

assignments_blueprint = """

	root {
		id: integer,
		name: string
	} []

"""

@pavao.generatesJson(string=assignments_blueprint)
async def process(request, response, db_connection, path_variables):
	userId = path_variables['user']

	result = list()
	for classId, className in await db_connection.fetch(list_assignments, userId):
		entry = {'id': classId, 'name': className}
		result.append(entry)

	return result


async def pavao_endpoint(db_connection, parameters):
	func_name = await localize_functionality("LIST_ASSIGNMENTS",
		db_connection, parameters)

	return {
		'method': 'GET',
		'path': '/access/assignments/{user:int}',
		'functionality': func_name,
		'processor': process
	}

