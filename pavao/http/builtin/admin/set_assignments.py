
import asyncio
import asyncpg
import pavao

from admin.common import localize_functionality

grant_query = """

	WITH to_add AS (
		SELECT cls.id FROM pavao.class cls
			WHERE cls.id = any($1::INTEGER[]) AND
			NOT cls.admin
	)
	
	INSERT INTO pavao.assignment (cls, account)
		SELECT collected.id, $2 FROM to_add collected
		ON CONFLICT DO NOTHING;

"""

revoke_query = """

	WITH to_remove AS (
		SELECT cls.id FROM pavao.class cls
			WHERE NOT cls.id = any($1::INTEGER[]) AND
			NOT cls.admin
	)

	DELETE FROM pavao.assignment assign WHERE
		assign.cls IN (SELECT id FROM to_remove) AND
		assign.account = $2;

"""

classes_list = """

	root integer[]

"""


@pavao.acceptsJson(string=classes_list)
async def process(request, response, parsed_json, path_variables, db_connection):
	userId = path_variables['user']
	classes = parsed_json

	userId = int(raw_userId)
	async with db_connection.transaction():
		await db_connection.execute(grant_query, classes, userId)
		await db_connection.execute(revoke_query, classes, userId)


async def pavao_endpoint(db_connection, parameters):
	func_name = await localize_functionality("SET_ASSIGNMENTS",
		db_connection, parameters)

	return {
		'method': 'PUT',
		'path': '/admin/assignments/{user:int}',
		'functionality': func_name,
		'processor': process
	}

