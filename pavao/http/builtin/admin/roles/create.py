
import asyncio
import asyncpg
import pavao

from admin.common import localize_functionality, capitalize
from admin.common import message_localization

add_role = """

	INSERT INTO
		pavao."role" (name, description)
		VALUES ($1, $2)
		RETURNING id;

"""

role_blueprint = """

	root {
		name: string (minLength=2),
		optional description: string
	}

"""

@pavao.generatesJson(stringBlueprint="root integer")
@pavao.acceptsJson(stringBlueprint=role_blueprint)
async def process(request, response, parsed_json, db_connection):
	localizer = message_localization().create_localizer(request)

	description = (parsed_json.description.strip()
		if pavao.has_optional_field(parsed_json, 'description')
		else None)

	try:
		roleId = await db_connection.fetchval(add_role,
			capitalize(parsed_json.name),
			description)

	except asyncpg.UniqueViolationError as e:
		response.set_status(409)
		return localizer.create_error("ROLE_EXISTS")

	except asyncpg.PostgresError as e:
		pavao.Logger.error(f"Error creating class: {e}")
		response.set_status(500)

		return localizer.create_error("UNEXPECTED_ERROR")

	response.set_status(201)
	return roleId


async def pavao_endpoint(db_connection, parameters):
	package_name, func_name = await localize_functionality("CREATE_ROLES",
		db_connection, parameters)

	return {
		'method': 'POST',
		'path': '/admin/roles',
		'package': package_name,
		'functionality': func_name,
		'processor': process
	}

