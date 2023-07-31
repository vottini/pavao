
import asyncio
import pavao

from admin.common import localize_functionality

list_classes = """

  SELECT id, name, description
    FROM pavao.class
    WHERE NOT admin;

"""

class_blueprint = """

  root {
    id: integer,
    name: string,
    optional description: string
  } []

"""

def mapClass(classData):

	result = {
		"id": classData['id'],
		"name": classData['name']
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
		'path': '/admin/classes',
		'functionality': func_name,
		'processor': process
	}

