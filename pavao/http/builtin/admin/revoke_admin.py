
import asyncio
import pavao

from admin.common import localize_functionality

remove_admin = """

	DELETE FROM pavao.assignment WHERE
		cls in (SELECT id FROM pavao.class WHERE admin) AND
		account = $1;

"""

async def process(request, response, db_connection, path_variables):
	await db_connection.execute(remove_admin,
		path_variables['user'])


async def pavao_endpoint(db_connection, parameters):
	func_name = await localize_functionality("REMOVE_ADMIN",
		db_connection, parameters)

	return {
		'method': 'DELETE',
		'path': '/admin/admins/{user:int}',
		'functionality': func_name,
		'processor': process
	}

