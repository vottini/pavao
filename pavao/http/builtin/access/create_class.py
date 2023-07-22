
import asyncio
import pavao

from access.registering import localize_functionality

add_class = """

	INSERT INTO
		pavao.class (name, description)
		VALUES ($1, $2);

"""

class_blueprint = """

	root {
		name: string (minLength=2),
		optional description: string
	}

"""

@pavao.acceptsJson(string=class_blueprint)
async def process(parsed_json, response, db_connection):
	query_args = (parsed_json['name'], parsed_json.get['description'])

	try:
		classId = await db_connection.execute(add_authentication, *query_args)

	response.set_status(201)


async def pavao_endpoint(db_connection, parameters):
	func_name = await localize_functionality("CREATE_CLASSES",
		db_connection, parameters)

	return {
		'method': 'POST',
		'path': '/access/class',
		'functionality': func_name,
		'processor': process
	}

