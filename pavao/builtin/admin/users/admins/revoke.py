
import asyncio
import pavao

from admin.common import localizer
from admin.common import create_message_localizer
from admin.common import assert_admin_access

remove_admin = """

	DELETE FROM pavao.assignment
		WHERE account = $1 AND "role" in (
			SELECT id FROM pavao."role"
				WHERE admin
		)

		RETURNING account;

"""

async def process(request, response, db_connection, path_variables, auth_data):
	message_localizer = create_message_localizer(request)
	revoked_user = path_variables['user']

	if auth_data.account_id == revoked_user:
		message_localizer.assign_response_error(response, "REVOKE_OWN_USER")
		response.set_status(403)
		return

	revoked = await db_connection.fetch(
		remove_admin, revoked_user)

	if len(revoked) == 0:
		message_localizer.assign_response_error(response, "USER_NOT_FOUND")
		response.set_status(404)


@assert_admin_access
def pavao_endpoint():

	return {
		'method': 'DELETE',
		'path': '/admin/users/admins/{user:int}',
		'package': localizer.map("PACKAGE"),
		'functionality': localizer.map("MODIFY_ADMIN"),
		'processor': process
	}

