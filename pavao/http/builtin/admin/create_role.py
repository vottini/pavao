
import asyncio
import asyncpg
import pavao

from admin.common import localize_functionality, capitalize

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

class_id = "root integer"
localized_messages = pavao.include('messages.ini')
localization = pavao.Localization(localized_messages)

@pavao.generatesJson(stringBlueprint=class_id)
@pavao.acceptsJson(stringBlueprint=role_blueprint)
async def process(request, response, parsed_json, db_connection):
	localizer = localization.create_localizer(request)

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
	func_name = await localize_functionality("CREATE_ROLES",
		db_connection, parameters)

	return {
		'method': 'POST',
		'path': '/admin/roles',
		'functionality': func_name,
		'processor': process
	}

