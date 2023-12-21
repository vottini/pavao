
import asyncio
import pavao

delete_query = """

	DELETE FROM pavao."role"
		WHERE id = $1
		RETURNING id;

"""

async def process(request, response, db_connection, path_variables, handler):

	try:
		deleted = await db_connection.fetchval(delete_query,
			path_variables['roleId'] )

		if deleted is None:
			response.set_status(404)
			return

		#authorizer = handler.authorizer
		#await authorizer.enable_functionality(db_connection,
		#	updated_functionality)

	except Exception as e:
		print(e)
		response.set_status(403)
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

