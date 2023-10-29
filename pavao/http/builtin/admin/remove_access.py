
import asyncio
import pavao

disallow_query = """

	DELETE FROM pavao."access"
		WHERE
			"role" = $1 AND
			functionality = $2;

"""

async def process(request, response, db_connection, path_variables, handler):
	role_id = path_variables['roleId']
	func_id = path_variables['functionalityId']

	try:
		await db_connection.execute(disallow_query,
			role_id, func_id)

		#authorizer = handler.authorizer
		#await authorizer.enable_functionality(db_connection,
		#	updated_functionality)

	except Exception as e:
		print(e)
		response.set_status(403)
		return


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

