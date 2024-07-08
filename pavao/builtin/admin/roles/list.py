
import asyncio
import pavao

from admin.common import localizer
from admin.common import assert_admin_access

list_roles = """

  SELECT
		id,
		name,
		description

    FROM pavao."role"
    WHERE NOT admin;

"""

role_blueprint = """

  root {
    id: integer,
    name: string,
    description: nullable string
  } []

"""

@pavao.generates_json(string_blueprint=role_blueprint)
async def process(request, db_connection):
	result = await db_connection.fetch(list_roles)
	return [ pavao.assemble_dicts(row) for row in result ]


@assert_admin_access
def pavao_endpoint():

	return {
		'method': 'GET',
		'path': '/admin/roles',
		'package': localizer.map("PACKAGE"),
		'functionality': localizer.map("LIST_ROLES"),
		'processor': process
	}

