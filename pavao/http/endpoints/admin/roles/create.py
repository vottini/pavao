
import asyncio
import asyncpg
import pavao

from admin.common import localize_functionality, capitalize
from admin.common import create_message_localizer

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

@pavao.generates_json(string_blueprint="root integer")
@pavao.accepts_json(string_blueprint=role_blueprint)
async def process(request, response, parsed_json, db_connection):
	localizer = create_message_localizer(request)

	description = (parsed_json.description.strip()
		if pavao.has_optional_field(parsed_json, 'description')
		else None)

	try:
		roleId = await db_connection.fetchval(add_role,
			capitalize(parsed_json.name),
			description)

	except asyncpg.UniqueViolationError as e:
		response.set_status(409)
		return localizer.create_error(
			"ROLE_EXISTS"
		)

	except asyncpg.PostgresError as e:
		pavao.Logger.error(f"Error creating class: {e}")

		response.set_status(500)
		return localizer.create_error(
			"UNEXPECTED_ERROR"
		)

	response.set_status(201)
	return roleId


async def pavao_endpoint(db_connection, persisted_settings):
	package_name, func_name = await localize_functionality("CREATE_ROLES",
		db_connection, persisted_settings)

	return {
		'method': 'POST',
		'path': '/admin/roles',
		'package': package_name,
		'functionality': func_name,
		'processor': process
	}

