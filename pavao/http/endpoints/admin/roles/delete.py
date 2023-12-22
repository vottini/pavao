
import asyncio
import pavao

from admin.common import create_message_localizer

delete_query = """

	DELETE FROM pavao."role"
		WHERE id = $1
		RETURNING id;

"""

async def process(request, response, db_connection, path_variables, handler):
	localizer = create_message_localizer(request)

	try:
		deleted = await db_connection.fetchval(delete_query,
			path_variables['roleId'])

		if deleted is None:
			localizer.assign_response_error(response, "ROLE_NOT_FOUND")
			response.set_status(404)
			return

		response.set_status(204)

	except Exception as e:
		pavao.Logger.error(f"Internal error updating role: {e}")
		localizer.assign_response_error(response, "UNEXPECTED_ERROR")
		response.set_status(500)
		return


from admin.common import localize_functionality
async def pavao_endpoint(db_connection, parameters):
	package_name, func_name = await localize_functionality("CREATE_ROLES",
		db_connection, parameters)

	return {
		'method': 'DELETE',
		'path': '/admin/roles/{roleId:int}',
		'package': package_name,
		'functionality': func_name,
		'processor': process
	}

