
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

localized_messages = pavao.include('messages.ini')
localization = pavao.Localization(localized_messages)

@pavao.generatesJson(string=assignments_blueprint)
async def process(request, response, db_connection, path_variables):
	localizer = localization.create_localizer(request)
	raw_userId = path_variables['user']

	try:
		userId = int(raw_userId)
		userData = await db_connection.fetchrow(find_user, userId)

	except ValueError as e:
		response.set_status(400)
		return {'error': localizer.get_message("INVALID_USERID")}

	if userData is None:
		response.set_status(404)
		return {'error': localizer.get_message("USER_INEXISTENT")}

	result = list()
	accesses = await db_connection.fetch(list_assignments, userId)
	for classId, className in accesses:
		entry = {'id': classId, 'name': className}
		result.append(entry)

	return result


async def pavao_endpoint(db_connection, parameters):
	func_name = await localize_functionality("LIST_ASSIGNMENTS",
		db_connection, parameters)

	return {
		'method': 'GET',
		'path': '/access/assignments/{user}',
		'functionality': func_name,
		'processor': process
	}

