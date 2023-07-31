
import asyncio
import asyncpg
import pavao

from admin.common import localize_functionality

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
	classId = path_variables['class']
	functionalities = parsed_json

	async with db_connection.transaction():
		await db_connection.execute(grant_query, functionalities, classId)
		await db_connection.execute(revoke_query, functionalities, classId)


async def pavao_endpoint(db_connection, parameters):
	func_name = await localize_functionality("SET_ACCESSES",
		db_connection, parameters)

	return {
		'method': 'PUT',
		'path': '/admin/accesses/{class:int}',
		'functionality': func_name,
		'processor': process
	}

