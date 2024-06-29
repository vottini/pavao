
import asyncio
import pavao

from admin.common import localizer
from admin.common import create_message_localizer
from admin.common import assert_admin_access

disallow_query = """

	DELETE FROM pavao."access"
		WHERE functionality = $1 AND "role" = $2
		RETURNING "role";

"""

async def process(request, response, db_connection, path_variables, server):
	message_localizer = create_message_localizer(request)

	try:
		deleted = await db_connection.fetchval(disallow_query,
			path_variables['functionality'],
			path_variables['role'])

		if deleted is None:
			response.set_status(404)
			message_localizer.assign_response_error(response, "ROLE_NOT_FOUND")
			return

		authorizer = server.authorizer
		await authorizer.remove_access(db_connection,
			path_variables['functionality'],
			path_variables['role'])

	except Exception as e:
		pavao.Logger.error(f"Internal error removing role access: {e}")
		message_localizer.assign_response_error(response, "UNEXPECTED_ERROR")
		response.set_status(500)


@assert_admin_access
def pavao_endpoint():

	return {
		'method': 'DELETE',
		'path': '/admin/roles/{role:int}/access/{functionality:int}',
		'package': localizer.map("PACKAGE"),
		'functionality': localizer.map("SET_ACCESSES"),
		'processor': process
	}

