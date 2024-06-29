
import asyncio
import pavao

from admin.common import localizer
from admin.common import assert_admin_access

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
	await db_connection.execute(add_admin, path_variables['user'])


@assert_admin_access
def pavao_endpoint():

	return {
		'method': 'PUT',
		'path': '/admin/users/admins/{user:int}',
		'package': localizer.map("PACKAGE"),
		'functionality': localizer.map("MODIFY_ADMIN"),
		'processor': process
	}

