
import asyncio
import pavao

from admin.common import localize_functionality
from admin.common import create_message_localizer

disable_user = """

	UPDATE pavao.account
		SET active = FALSE
		WHERE id = $1
		RETURNING id;

"""

async def process(request, response, db_connection, path_variables, auth_data):
	localizer = create_message_localizer(request)
	disabled_user = path_variables['user']

	if auth_data.account_id == disabled_user:
		localizer.assign_response_error(response, "DISABLE_OWN_USER")
		response.set_status(403)
		return

	disabled = await db_connection.execute(
		disable_user, disabled_user)

	if len(disabled) == 0:
		localizer.assign_response_error(response, "USER_NOT_FOUND")
		response.set_status(404)


async def pavao_endpoint(db_connection, persisted_settings):
	package_name, func_name = await localize_functionality("ENABLE_USERS",
		db_connection, persisted_settings)

	return {
		'method': 'DELETE',
		'path': '/admin/users/{user:int}/active',
		'package': package_name,
		'functionality': func_name,
		'processor': process
	}

