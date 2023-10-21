
import asyncio
import asyncpg
import pavao

from admin.common import localize_functionality

grant_query = """

	WITH to_add AS (
		SELECT acc.id FROM pavao.account acc
			WHERE acc.id = any($1::INTEGER[])
	)
	
	INSERT INTO pavao.assignment (account, "role")
		SELECT collected.id, $2 FROM to_add collected
		ON CONFLICT DO NOTHING;

"""

revoke_query = """

	WITH to_remove AS (
		SELECT acc.id FROM pavao.account acc
			WHERE NOT acc.id = any($1::INTEGER[])
	)

	DELETE FROM pavao.assignment assign WHERE
		assign.account IN (SELECT id FROM to_remove) AND
		assign."role" = $2;

"""

user_list = """

	root integer[]

"""


@pavao.acceptsJson(stringBlueprint=user_list)
async def process(request, response, parsed_json, path_variables, db_connection):
	role_id = path_variables['role']
	users = parsed_json

	async with db_connection.transaction():
		await db_connection.execute(grant_query, users, role_id)
		await db_connection.execute(revoke_query, users, role_id)


async def pavao_endpoint(db_connection, parameters):
	func_name = await localize_functionality("SET_ASSIGNMENTS",
		db_connection, parameters)

	return {
		'method': 'PUT',
		'path': '/admin/assignments/role/{role:int}',
		'functionality': func_name,
		'processor': process
	}

