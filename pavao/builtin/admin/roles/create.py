
import asyncio
import asyncpg
import pavao

from admin.common import localizer
from admin.common import create_message_localizer
from admin.common import assert_admin_access
from admin.common import capitalize

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
	message_localizer = create_message_localizer(request)

	description = (parsed_json.description.strip()
		if pavao.has_optional_field(parsed_json, 'description')
		else None)

	try:
		roleId = await db_connection.fetchval(add_role,
			capitalize(parsed_json.name),
			description)

	except asyncpg.UniqueViolationError as e:
		response.set_status(409)
		return message_localizer.create_error(
			"ROLE_EXISTS"
		)

	except asyncpg.PostgresError as e:
		pavao.Logger.error(f"Error creating class: {e}")

		response.set_status(500)
		return message_localizer.create_error(
			"UNEXPECTED_ERROR"
		)

	response.set_status(201)
	return roleId


@assert_admin_access
def pavao_endpoint():

	return {
		'method': 'POST',
		'path': '/admin/roles',
		'package': localizer.map("PACKAGE"),
		'functionality': localizer.map("CREATE_ROLES"),
		'processor': process
	}

