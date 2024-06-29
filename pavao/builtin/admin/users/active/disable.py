
import asyncio
import pavao

from admin.common import localizer
from admin.common import create_message_localizer
from admin.common import assert_admin_access

disable_user = """

	UPDATE pavao.account
		SET active = FALSE
		WHERE id = $1
		RETURNING id;

"""

async def process(request, response, db_connection, path_variables, auth_data):
	message_localizer = create_message_localizer(request)
	disabled_user = path_variables['user']

	if auth_data.account_id == disabled_user:
		message_localizer.assign_response_error(response, "DISABLE_OWN_USER")
		response.set_status(403)
		return

	disabled = await db_connection.execute(
		disable_user, disabled_user)

	if len(disabled) == 0:
		message_localizer.assign_response_error(response, "USER_NOT_FOUND")
		response.set_status(404)


@assert_admin_access
def pavao_endpoint():

	return {
		'method': 'DELETE',
		'path': '/admin/users/{user:int}/active',
		'package': localizer.map("PACKAGE"),
		'functionality': localizer.map("EDIT_USERS"),
		'processor': process
	}

