
import asyncio
import pavao

allow_query = """

	INSERT INTO pavao."access" ("role", functionality)
		VALUES ($1, $2)

"""

async def process(request, response, db_connection, path_variables, handler):
	role_id = path_variables['roleId']
	func_id = path_variables['functionalityId']

	try:
		await db_connection.execute(allow_query,
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
		'method': 'PUT',
		'path': '/admin/roles/{roleId:int}/access/{functionalityId:int}',
		'package': package_name,
		'functionality': func_name,
		'processor': process
	}

