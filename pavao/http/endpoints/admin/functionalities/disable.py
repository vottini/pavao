
import asyncio
import pavao

check_admin = """

	SELECT COUNT(*) FROM
		pavao.functionality func
			INNER JOIN pavao."access" acc ON acc.functionality = func.id 
			INNER JOIN pavao."role" rl ON acc."role" = rl.id

		WHERE
			func.id = $1 AND 
			rl.admin;

"""

disable_funcionality_query = """

	UPDATE pavao.functionality 
		SET enabled = FALSE 
		WHERE id = $1
		RETURNING name;

"""

async def process(request, response, db_connection, path_variables, handler):
	functionality_id = path_variables['functionalityId']
	admin_roles = await db_connection.fetchval(check_admin,
		functionality_id)

	if admin_roles > 0:
		response.set_status(403)
		return

	updated_functionality = await db_connection.fetchval(
		disable_funcionality_query,
		functionality_id)

	if updated_functionality is None:
		response.set_status(404)
		return

	authorizer = handler.authorizer
	authorizer.disable_functionality(
		updated_functionality)


from admin.common import localize_functionality
async def pavao_endpoint(db_connection, parameters):
	package_name, func_name = await localize_functionality("MANAGE_FUNCTIONALITIES",
		db_connection, parameters)

	return {
		'method': 'PUT',
		'path': '/admin/functionalities/{functionalityId:int}/disable',
		'package': package_name,
		'functionality': func_name,
		'processor': process
	}

