
import asyncio
import pavao

from access.registering import localize_functionality
list_classes = "SELECT name, description, admin FROM pavao.class;"

class_blueprint = """

  root {
    name: string,
    optional description: string,
    isAdmin: bool
  } []

"""

def mapClass(classData):

	result = {
		"name": classData['name'],
		"isAdmin": classData['admin']
	}

	description = classData['description']
	if description is not None:
		result['description'] = description

	return result


@pavao.generatesJson(string=class_blueprint)
async def process(request, db_connection):
	result = await db_connection.fetch(list_classes)
	return [ mapClass(row) for row in result ]


async def pavao_endpoint(db_connection, parameters):
	func_name = await localize_functionality("LIST_CLASSES",
		db_connection, parameters)

	return {
		'method': 'GET',
		'path': '/access/classes',
		'functionality': func_name,
		'processor': process
	}

