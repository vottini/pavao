
import asyncio
import asyncpg
import pavao

from admin.common import localize_functionality
from admin.common import create_message_localizer

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


@pavao.accepts_json(string_blueprint=roles_list)
async def process(handler, response, parsed_json, path_variables, db_connection):
	user_id = path_variables['user']
	roles = parsed_json

	try:
		async with db_connection.transaction():
			await db_connection.execute(grant_query, roles, user_id)
			await db_connection.execute(revoke_query, roles, user_id)

		handler.authorizer.mark_modified(user_id)

	except asyncpg.ForeignKeyViolationError:
		localizer.assign_response_error(response, "USER_NOT_FOUND")
		response.set_status(404)

	except Exception as e:
		pavao.Logger.error(f"Internal error assigning user: {e}")
		localizer.assign_response_error(response, "UNEXPECTED_ERROR")
		response.set_status(500)

	response.set_status(204)


async def pavao_endpoint(db_connection, persisted_settings):
	package_name, func_name = await localize_functionality("SET_ASSIGNMENTS",
		db_connection, persisted_settings)

	return {
		'method': 'PUT',
		'path': '/admin/users/{user:int}/assignments',
		'package': package_name,
		'functionality': func_name,
		'processor': process
	}

