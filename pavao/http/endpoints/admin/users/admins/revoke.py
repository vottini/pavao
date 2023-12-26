
import asyncio
import pavao

from admin.common import localize_functionality
from admin.common import create_message_localizer

remove_admin = """

	DELETE FROM pavao.assignment
		WHERE account = $1 AND "role" in (
			SELECT id FROM pavao."role"
				WHERE admin
		)

		RETURNING account;

"""

async def process(request, response, db_connection, path_variables, auth_data):
	localizer = create_message_localizer(request)
	revoked_user = path_variables['user']

	if auth_data.account_id == revoked_user:
		localizer.assign_response_error(response, "REVOKE_OWN_USER")
		response.set_status(403)
		return

	revoked = await db_connection.fetch(
		remove_admin, revoked_user)

	if len(revoked) == 0:
		localizer.assign_response_error(response, "USER_NOT_FOUND")
		response.set_status(404)


async def pavao_endpoint(db_connection, persisted_settings):
	package_name, func_name = await localize_functionality("MODIFY_ADMIN",
		db_connection, persisted_settings)

	return {
		'method': 'DELETE',
		'path': '/admin/users/admins/{user:int}',
		'package': package_name,
		'functionality': func_name,
		'processor': process
	}

