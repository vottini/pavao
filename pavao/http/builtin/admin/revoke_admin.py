
import asyncio
import pavao

from admin.common import localize_functionality

remove_admin = """

	DELETE FROM pavao.assignment WHERE
		"role" in (SELECT id FROM pavao."role" WHERE admin) AND
		account = $1;

"""

async def process(request, response, db_connection, path_variables):
	await db_connection.execute(remove_admin,
		path_variables['user'])


async def pavao_endpoint(db_connection, parameters):
	package_name, func_name = await localize_functionality("MODIFY_ADMIN",
		db_connection, parameters)

	return {
		'method': 'DELETE',
		'path': '/admin/admins/{user:int}',
		'package': package_name,
		'functionality': func_name,
		'processor': process
	}

