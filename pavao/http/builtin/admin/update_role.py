
import asyncio
import asyncpg
import pavao

from admin.common import localize_functionality

options_blueprint = """

	root {
		optional name: string (minLength=2),
		optional description: string
	}

"""

localized_messages = pavao.include('messages.ini')
localization = pavao.Localization(localized_messages)

@pavao.acceptsJson(stringBlueprint=options_blueprint)
async def process(request, response, parsed_json, db_connection, path_variables):
	localizer = localization.create_localizer(request)
	roleId = path_variables['role']

	async with db_connection.transaction():
		for column in ("name", "description"):
			if not pavao.has_optional_field(parsed_json, column):
				continue

			query = f"""

				UPDATE pavao."role"
					set {column} = $1
					WHERE id = $2;

			"""

			try:
				await db_connection.execute(query,
					getattr(parsed_json, column),
					roleId)

			except asyncpg.UniqueViolationError as e:
				response.set_status(409)
				return localizer.create_error("ROLE_EXISTS")

			except asyncpg.PostgresError as e:
				pavao.Logger.error(f"Internal error updating role: {e}")

				response.set_status(500)
				return localizer.create_error("UNEXPECTED_ERROR")

	response.set_status(204)


async def pavao_endpoint(db_connection, parameters):
	package_name, func_name = await localize_functionality("CREATE_ROLES",
		db_connection, parameters)

	return {
		'method': 'PATCH',
		'path': '/admin/roles/{role:int}',
		'package': package_name,
		'functionality': func_name,
		'processor': process
	}

