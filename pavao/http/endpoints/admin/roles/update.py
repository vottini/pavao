
import asyncio
import asyncpg
import pavao

from admin.common import localize_functionality
from admin.common import create_message_localizer

options_blueprint = """

	root {
		optional name: string (minLength=2),
		optional description: string
	}

"""


@pavao.accepts_json(string_blueprint=options_blueprint)
async def process(request, response, parsed_json, db_connection, path_variables):
	localizer = create_message_localizer(request)
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
					localizer.assign_response_error(response, "ROLE_NOT_FOUND")
					response.set_status(404)
					return

			except asyncpg.UniqueViolationError as e:
				localizer.assign_response_error(response, "ROLE_EXISTS")
				response.set_status(409)
				return

			except asyncpg.PostgresError as e:
				pavao.Logger.error(f"Internal error updating role: {e}")
				localizer.assign_response_error(response, "UNEXPECTED_ERROR")
				response.set_status(500)
				return

	response.set_status(204)


async def pavao_endpoint(db_connection, persisted_settings):
	package_name, func_name = await localize_functionality("CREATE_ROLES",
		db_connection, persisted_settings)

	return {
		'method': 'PATCH',
		'path': '/admin/roles/{role:int}',
		'package': package_name,
		'functionality': func_name,
		'processor': process
	}

