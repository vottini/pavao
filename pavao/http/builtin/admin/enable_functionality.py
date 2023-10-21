
import asyncio
import pavao

enable_query = """

	UPDATE pavao.functionality 
		SET enabled = TRUE 
		WHERE id = $1
		RETURNING id;

"""

async def process(request, response, db_connection, path_variables):
	updated = await db_connection.fetchval(enable_query,
		path_variables['functionality'])

	if updated is None:
		response.set_status(404)


from admin.common import localize_functionality
async def pavao_endpoint(db_connection, parameters):
	func_name = await localize_functionality("MANAGE_FUNCTIONALITIES",
		db_connection, parameters)

	return {
		'method': 'PUT',
		'path': '/admin/functionalities/enable/{functionality:int}',
		'functionality': func_name,
		'processor': process
	}

