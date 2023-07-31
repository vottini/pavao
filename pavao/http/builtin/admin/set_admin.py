
import asyncio
import pavao

from admin.common import localize_functionality

add_admin = """

	WITH found_user AS (
		SELECT id FROM pavao.account
			WHERE id = $1
	)

	INSERT INTO pavao.assignment (account, cls)
		SELECT found.id, cls.id
				FROM found_user found
				CROSS JOIN pavao.class cls
				WHERE cls.admin

		ON CONFLICT DO NOTHING;

"""

async def process(request, response, db_connection, path_variables):
	await db_connection.execute(add_admin,
		path_variables['user'])


async def pavao_endpoint(db_connection, parameters):
	func_name = await localize_functionality("ADD_ADMIN",
		db_connection, parameters)

	return {
		'method': 'PUT',
		'path': '/admin/admins/{user:int}',
		'functionality': func_name,
		'processor': process
	}

