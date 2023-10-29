
import asyncio
import pavao

enable_query = """

	UPDATE pavao.functionality 
		SET enabled = TRUE 
		WHERE id = $1
		RETURNING name;

"""

async def process(request, response, db_connection, path_variables, handler):
	updated_functionality = await db_connection.fetchval(enable_query,
		path_variables['functionalityId'])

	if updated_functionality is None:
		response.set_status(404)
		return

	authorizer = handler.authorizer
	await authorizer.enable_functionality(db_connection,
		updated_functionality)


from admin.common import localize_functionality
async def pavao_endpoint(db_connection, parameters):
	package_name, func_name = await localize_functionality("MANAGE_FUNCTIONALITIES",
		db_connection, parameters)

	return {
		'method': 'PUT',
		'path': '/admin/functionalities/{functionalityId:int}/enable',
		'package': package_name,
		'functionality': func_name,
		'processor': process
	}

