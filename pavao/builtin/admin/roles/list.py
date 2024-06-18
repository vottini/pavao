
import asyncio
import pavao

from admin.common import localize_functionality

list_roles = """

  SELECT id, name, description
    FROM pavao."role"
    WHERE NOT admin;

"""

role_blueprint = """

  root {
    id: integer,
    name: string,
    optional description: string
  } []

"""

@pavao.generates_json(string_blueprint=role_blueprint)
async def process(request, db_connection):
	result = await db_connection.fetch(list_roles)
	return [ pavao.assemble_dicts(row) for row in result ]


async def pavao_endpoint(db_connection, persisted_settings):
	package_name, func_name = await localize_functionality("LIST_ROLES",
		db_connection, persisted_settings)

	return {
		'method': 'GET',
		'path': '/admin/roles',
		'package': package_name,
		'functionality': func_name,
		'processor': process
	}

