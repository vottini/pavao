
import asyncio
import pavao

from admin.common import localize_functionality
from admin.common import create_message_localizer

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
		localizer = create_message_localizer(request)
		localizer.assign_response_error(response, "FUNCTIONALITY_NOT_FOUND")
		response.set_status(404)
		return

	authorizer = handler.authorizer
	await authorizer.enable_functionality(db_connection,
		updated_functionality)


async def pavao_endpoint(db_connection, persisted_settings):
	package_name, func_name = await localize_functionality("MANAGE_FUNCTIONALITIES",
		db_connection, persisted_settings)

	return {
		'method': 'PUT',
		'path': '/admin/functionalities/{functionalityId:int}/enable',
		'package': package_name,
		'functionality': func_name,
		'processor': process
	}

