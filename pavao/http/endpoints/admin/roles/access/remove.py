
import asyncio
import pavao

from admin.common import create_message_localizer

disallow_query = """

	DELETE FROM pavao."access"
		WHERE functionality = $1 AND "role" = $2
		RETURNING id;

"""

async def process(request, response, db_connection, path_variables, handler):
	localizer = create_message_localizer(request)

	try:
		deleted = await db_connection.fetchval(disallow_query,
			path_variables['functionalityId'],
			path_variables['roleId'])

		if deleted is None:
			localizer.assign_response_error(response, "ROLE_NOT_FOUND")
			response.set_status(404)
			return

		#authorizer = handler.authorizer
		#await authorizer.enable_functionality(db_connection,
		#	updated_functionality)

	except Exception as e:
		pavao.Logger.error(f"Internal error removing role access: {e}")
		localizer.assign_response_error(response, "UNEXPECTED_ERROR")
		response.set_status(500)


from admin.common import localize_functionality
async def pavao_endpoint(db_connection, parameters):
	package_name, func_name = await localize_functionality("SET_ACCESSES",
		db_connection, parameters)

	return {
		'method': 'DELETE',
		'path': '/admin/roles/{roleId:int}/access/{functionalityId:int}',
		'package': package_name,
		'functionality': func_name,
		'processor': process
	}

