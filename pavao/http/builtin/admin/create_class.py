
import asyncio
import asyncpg
import pavao

from admin.common import localize_functionality, capitalize

add_class = """

	INSERT INTO
		pavao.class (name, description)
		VALUES ($1, $2)
		RETURNING id;

"""

class_blueprint = """

	root {
		name: string (minLength=2),
		optional description: string
	}

"""

class_id = "root integer"
localized_messages = pavao.include('messages.ini')
localization = pavao.Localization(localized_messages)

@pavao.generatesJson(string=class_id)
@pavao.acceptsJson(string=class_blueprint)
async def process(request, response, parsed_json, db_connection):
	localizer = localization.create_localizer(request)
	description = parsed_json.get('description')
	description = description.strip() if description is not None else None

	try:
		classId = await db_connection.fetchval(add_class,
			capitalize(parsed_json['name']),
			description)

	except asyncpg.UniqueViolationError as e:
		response.set_status(409)
		return {"error": localizer.get_message("CLASS_EXISTS")}

	except asyncpg.PostgresError as e:
		msg = f"Error creating class: {e}"
		pavao.Logger.error(msg)

		response.set_status(500)
		return {"error": localizer.get_message("UNEXPECTED_ERROR")}

	response.set_status(201)
	return classId


async def pavao_endpoint(db_connection, parameters):
	func_name = await localize_functionality("CREATE_CLASSES",
		db_connection, parameters)

	return {
		'method': 'POST',
		'path': '/admin/classes',
		'functionality': func_name,
		'processor': process
	}

