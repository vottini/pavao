
import asyncio
import asyncpg
import pavao

from access.registering import localize_functionality

grant_query = """

	WITH to_add AS (
		SELECT func.id FROM pavao.functionality func
			WHERE func.name = any($1::TEXT[])
	)
	
	INSERT INTO pavao.access (functionality, cls)
		SELECT collected.id, $2 FROM to_add collected
		ON CONFLICT DO NOTHING;

"""

revoke_query = """

	WITH to_remove AS (
		SELECT id FROM pavao.functionality func
			WHERE NOT func.name = any($1::TEXT[])
	)

	DELETE FROM pavao.access acs WHERE
		acs.functionality IN (SELECT id FROM to_remove) AND
		acs.cls = $2;

"""

functionalities_list = """

	root string (minLength=2) []

"""


@pavao.acceptsJson(string=functionalities_list)
async def process(request, response, parsed_json, path_variables, db_connection):
	raw_classId = path_variables['class']
	functionalities = parsed_json

	try:
		classId = int(raw_classId)
		async with db_connection.transaction():
			await db_connection.execute(grant_query, functionalities, classId)
			await db_connection.execute(revoke_query, functionalities, classId)

	except ValueError as e:
		response.set_status(400)
		return


async def pavao_endpoint(db_connection, parameters):
	func_name = await localize_functionality("SET_ACCESSES",
		db_connection, parameters)

	return {
		'method': 'PUT',
		'path': '/access/accesses/{class}',
		'functionality': func_name,
		'processor': process
	}

