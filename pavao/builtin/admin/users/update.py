
import asyncio
import asyncpg
import humps
import pavao

from admin.common import localize_functionality
from admin.common import create_message_localizer

options_blueprint = """

	root {
		optional login: string (minLength=4),
		optional firstName: string (minLength=2),
		optional lastName: nullable string (minLength=2)
	}

"""


@pavao.accepts_json(string_blueprint=options_blueprint)
async def process(request, response, parsed_json, db_connection, path_variables):
	localizer = create_message_localizer(request)
	userId = path_variables['userId']

	async with db_connection.transaction():
		for column in ("login", "firstName", "lastName"):
			if not pavao.has_optional_field(parsed_json, column):
				continue

			snake_case_column = humps.decamelize(column)

			query = f"""

				UPDATE pavao."account"
					set {snake_case_column} = $1
					WHERE
						id = $2 AND
						COALESCE({snake_case_column}, '') <> COALESCE($1, '');

			"""

			try:
				await db_connection.execute(query,
					getattr(parsed_json, column),
					userId)

			except asyncpg.UniqueViolationError as e:
				localizer.assign_response_error(response, "LOGIN_EXISTS")
				response.set_status(409)
				return

			except asyncpg.PostgresError as e:
				pavao.Logger.error(f"Internal error updating role: {e}")
				localizer.assign_response_error(response, "UNEXPECTED_ERROR")
				response.set_status(500)
				return

	response.set_status(204)


async def pavao_endpoint(db_connection, persisted_settings):
	package_name, func_name = await localize_functionality("CREATE_USERS",
		db_connection, persisted_settings)

	return {
		'method': 'PATCH',
		'path': '/admin/users/{userId:int}',
		'package': package_name,
		'functionality': func_name,
		'processor': process
	}

