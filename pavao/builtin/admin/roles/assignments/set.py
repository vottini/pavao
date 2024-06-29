
import asyncio
import asyncpg
import pavao

from admin.common import localizer
from admin.common import create_message_localizer
from admin.common import assert_admin_access

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


@pavao.accepts_json(string_blueprint=user_list)
async def process(request, response, parsed_json, path_variables, db_connection):
	role_id = path_variables['role']
	users = parsed_json

	try:
		async with db_connection.transaction():
			await db_connection.execute(grant_query, users, role_id)
			await db_connection.execute(revoke_query, users, role_id)

	except asyncpg.ForeignKeyViolationError:
		message_localizer = create_message_localizer(request)
		localizer.assign_response_error(response, "ROLE_NOT_FOUND")
		response.set_status(404)


@assert_admin_access
def pavao_endpoint():

	return {
		'method': 'PUT',
		'path': '/admin/roles/{role:int}/assignments',
		'package': localizer.map("PACKAGE"),
		'functionality': localizer.map("SET_ASSIGNMENTS"),
		'processor': process
	}

