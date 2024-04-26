
import asyncio
import pavao

from admin.common import localize_functionality
from admin.common import create_message_localizer

disallow_query = """

	DELETE FROM pavao."access"
		WHERE functionality = $1 AND "role" = $2
		RETURNING "role";

"""

async def process(request, response, db_connection, path_variables, server):
	localizer = create_message_localizer(request)

	try:
		deleted = await db_connection.fetchval(disallow_query,
			path_variables['functionality'],
			path_variables['role'])

		if deleted is None:
			localizer.assign_response_error(response, "ROLE_NOT_FOUND")
			response.set_status(404)
			return

		authorizer = server.authorizer
		await authorizer.remove_access(db_connection,
			path_variables['functionality'],
			path_variables['role'])

		response.set_status(204)

	except Exception as e:
		pavao.Logger.error(f"Internal error removing role access: {e}")
		localizer.assign_response_error(response, "UNEXPECTED_ERROR")
		response.set_status(500)


async def pavao_endpoint(db_connection, persisted_settings):
	package_name, func_name = await localize_functionality("SET_ACCESSES",
		db_connection, persisted_settings)

	return {
		'method': 'DELETE',
		'path': '/admin/roles/{role:int}/access/{functionality:int}',
		'package': package_name,
		'functionality': func_name,
		'processor': process
	}

