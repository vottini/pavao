
import asyncio
import pavao

from admin.common import localize_functionality

add_admin = """

	WITH found_user AS (
		SELECT id FROM pavao.account
			WHERE id = $1
	)

	INSERT INTO pavao.assignment (account, "role")
		SELECT found.id, rl.id
				FROM found_user found
				CROSS JOIN pavao."role" rl
				WHERE rl.admin

		ON CONFLICT DO NOTHING;

"""

async def process(request, response, db_connection, path_variables):
	await db_connection.execute(add_admin,
		path_variables['user'])


async def pavao_endpoint(db_connection, parameters):
	package_name, func_name = await localize_functionality("MODIFY_ADMIN",
		db_connection, parameters)

	return {
		'method': 'PUT',
		'path': '/admin/users/admins/{user:int}',
		'package': package_name,
		'functionality': func_name,
		'processor': process
	}

