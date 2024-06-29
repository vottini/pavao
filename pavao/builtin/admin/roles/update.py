
import asyncio
import asyncpg
import pavao

from admin.common import localizer
from admin.common import create_message_localizer
from admin.common import assert_admin_access

options_blueprint = """

	root {
		optional name: string (minLength=2),
		optional description: string
	}

"""


@pavao.accepts_json(string_blueprint=options_blueprint)
async def process(request, response, parsed_json, db_connection, path_variables):
	message_localizer = create_message_localizer(request)
	roleId = path_variables['role']

	async with db_connection.transaction():
		for column in ("name", "description"):
			if not pavao.has_optional_field(parsed_json, column):
				continue

			query = f"""

				UPDATE pavao."role"
					set {column} = $1
					WHERE id = $2
					RETURNING id;

			"""

			try:
				column_name = getattr(parsed_json, column)
				updated = await db_connection.fetchval(query,
					column_name, roleId)

				if updated is None:
					response.set_status(404)
					message_localizer.assign_response_error(response,
						"ROLE_NOT_FOUND")

			except asyncpg.UniqueViolationError as e:
				message_localizer.assign_response_error(response, "ROLE_EXISTS")
				response.set_status(409)
				return

			except asyncpg.PostgresError as e:
				pavao.Logger.error(f"Internal error updating role: {e}")
				message_localizer.assign_response_error(response, "UNEXPECTED_ERROR")
				response.set_status(500)
				return


@assert_admin_access
def pavao_endpoint():

	return {
		'method': 'PATCH',
		'path': '/admin/roles/{role:int}',
		'package': localizer.map("PACKAGE"),
		'functionality': localizer.map("CREATE_ROLES"),
		'processor': process
	}

