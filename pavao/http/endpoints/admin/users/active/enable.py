
import asyncio
import pavao

from admin.common import localize_functionality

enable_user = """

	UPDATE pavao.account
		SET active = TRUE
		WHERE id = $1
		RETURNING id;

"""

async def process(request, response, db_connection, path_variables):
	await db_connection.execute(enable_user,
		path_variables['userId'])


async def pavao_endpoint(db_connection, parameters):
	package_name, func_name = await localize_functionality("ENABLE_USERS",
		db_connection, parameters)

	return {
		'method': 'PUT',
		'path': '/admin/users/{userId:int}/active',
		'package': package_name,
		'functionality': func_name,
		'processor': process
	}

