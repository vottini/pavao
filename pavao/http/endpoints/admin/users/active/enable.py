
import asyncio
import pavao

from admin.common import localize_functionality
from admin.common import create_message_localizer

enable_user = """

	UPDATE pavao.account
		SET active = TRUE
		WHERE id = $1
		RETURNING id;

"""

async def process(request, response, db_connection, path_variables):
	localizer = create_message_localizer(request)
	enabled = await db_connection.fetchval(enable_user,
		path_variables['user'])

	if enabled is None:
		localizer.assign_response_error(response, "USER_NOT_FOUND")
		response.set_status(404)

	response.set_status(204)


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

