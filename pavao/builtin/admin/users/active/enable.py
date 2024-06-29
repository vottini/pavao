
import asyncio
import pavao

from admin.common import localizer
from admin.common import create_message_localizer
from admin.common import assert_admin_access

enable_user = """

	UPDATE pavao.account
		SET active = TRUE
		WHERE id = $1
		RETURNING id;

"""

async def process(request, response, db_connection, path_variables):
	message_localizer = create_message_localizer(request)
	enabled = await db_connection.fetchval(enable_user,
		path_variables['user'])

	if enabled is None:
		message_localizer.assign_response_error(response, "USER_NOT_FOUND")
		response.set_status(404)


@assert_admin_access
def pavao_endpoint():

	return {
		'method': 'PUT',
		'path': '/admin/users/{user:int}/active',
		'package': localizer.map("PACKAGE"),
		'functionality': localizer.map("EDIT_USERS"),
		'processor': process
	}

