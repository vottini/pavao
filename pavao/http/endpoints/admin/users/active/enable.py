
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
	updated = await db_connection.fetchval(enable_user,
		path_variables['user'])


async def pavao_endpoint(db_connection, persisted_settings):
	package_name, func_name = await localize_functionality("ENABLE_USERS",
		db_connection, persisted_settings)

	return {
		'method': 'PUT',
		'path': '/admin/users/{user:int}/active',
		'package': package_name,
		'functionality': func_name,
		'processor': process
	}

