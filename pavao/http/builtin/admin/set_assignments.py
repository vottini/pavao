
import asyncio
import asyncpg
import pavao

from admin.common import localize_functionality

grant_query = """

	WITH to_add AS (
		SELECT rl.id FROM pavao."role" rl
			WHERE rl.id = any($1::INTEGER[]) AND
			NOT rl.admin
	)
	
	INSERT INTO pavao.assignment ("role", account)
		SELECT collected.id, $2 FROM to_add collected
		ON CONFLICT DO NOTHING;

"""

revoke_query = """

	WITH to_remove AS (
		SELECT rl.id FROM pavao."role" rl
			WHERE NOT rl.id = any($1::INTEGER[]) AND
			NOT rl.admin
	)

	DELETE FROM pavao.assignment assign WHERE
		assign."role" IN (SELECT id FROM to_remove) AND
		assign.account = $2;

"""

roles_list = """

	root integer[]

"""


@pavao.acceptsJson(stringBlueprint=roles_list)
async def process(request, response, parsed_json, path_variables, db_connection):
	userId = path_variables['user']
	roles = parsed_json

	userId = int(raw_userId)
	async with db_connection.transaction():
		await db_connection.execute(grant_query, roles, userId)
		await db_connection.execute(revoke_query, roles, userId)


async def pavao_endpoint(db_connection, parameters):
	func_name = await localize_functionality("SET_ASSIGNMENTS",
		db_connection, parameters)

	return {
		'method': 'PUT',
		'path': '/admin/assignments/{user:int}',
		'functionality': func_name,
		'processor': process
	}

