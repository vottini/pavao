
import asyncio
import pavao

from admin.common import localize_functionality

list_users = """

  SELECT id, first_name, last_name, active
    FROM pavao.account
    WHERE NOT managerial
	ORDER BY first_name;

"""

user_blueprint = """

  root {
    id: integer,
    firstName: string,
    optional lastName: string,
	active: bool
  } []

"""

@pavao.generatesJson(stringBlueprint=user_blueprint)
async def process(request, response, db_connection):
	result = await db_connection.fetch(list_users)
	return [ pavao.assemble_dicts(row) for row in result ]


async def pavao_endpoint(db_connection, parameters):
	package_name, func_name = await localize_functionality("LIST_USERS",
		db_connection, parameters)

	return {
		'method': 'GET',
		'path': '/admin/users',
		'package': package_name,
		'functionality': func_name,
		'processor': process
	}

