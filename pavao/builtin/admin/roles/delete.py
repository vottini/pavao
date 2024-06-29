
import asyncio
import pavao

from admin.common import localizer
from admin.common import create_message_localizer
from admin.common import assert_admin_access

delete_query = """

	DELETE FROM pavao."role"
		WHERE id = $1
		RETURNING id;

"""

async def process(request, response, db_connection, path_variables):
	message_localizer = create_message_localizer(request)

	try:
		deleted = await db_connection.fetchval(delete_query,
			path_variables['roleId'])

		if deleted is None:
			response.set_status(404)
			message_localizer.assign_response_error(response,
				"ROLE_NOT_FOUND")

	except Exception as e:
		pavao.Logger.error(f"Internal error updating role: {e}")
		message_localizer.assign_response_error(response, "UNEXPECTED_ERROR")
		response.set_status(500)


@assert_admin_access
def pavao_endpoint():

	return {
		'method': 'DELETE',
		'path': '/admin/roles/{roleId:int}',
		'package': localizer.map("PACKAGE"),
		'functionality': localizer.map("CREATE_ROLES"),
		'processor': process
	}

