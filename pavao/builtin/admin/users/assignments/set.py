
import asyncio
import asyncpg
import pavao

from admin.common import localizer
from admin.common import create_message_localizer
from admin.common import assert_admin_access

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
async def process(server, request, response, parsed_json, path_variables, db_connection):
	message_localizer = create_message_localizer(request)
	user_id = path_variables['user']
	roles = parsed_json

	try:
		async with db_connection.transaction():
			await db_connection.execute(grant_query, roles, user_id)
			await db_connection.execute(revoke_query, roles, user_id)

		server.authorizer.mark_modified(user_id)

	except asyncpg.ForeignKeyViolationError:
		message_localizer.assign_response_error(response, "USER_NOT_FOUND")
		response.set_status(404)

	except Exception as e:
		pavao.Logger.error(f"Internal error assigning user: {e}")
		message_localizer.assign_response_error(response, "UNEXPECTED_ERROR")
		response.set_status(500)


@assert_admin_access
def pavao_endpoint():

	return {
		'method': 'PUT',
		'path': '/admin/users/{user:int}/assignments',
		'package': localizer.map("PACKAGE"),
		'functionality': localizer.map("SET_ASSIGNMENTS"),
		'processor': process
	}

