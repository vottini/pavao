
import asyncio
import asyncpg
import pavao

from admin.common import localize_functionality
from admin.common import create_message_localizer

allow_query = """

	INSERT INTO pavao."access" (functionality, "role")
		VALUES ($1, $2)

"""

async def process(request, response, db_connection, path_variables, handler):
	localizer = create_message_localizer(request)

	try:
		await db_connection.execute(allow_query,
			path_variables['functionalityId'],
			path_variables['roleId'])

		#authorizer = handler.authorizer
		#await authorizer.enable_functionality(db_connection,
		#	updated_functionality)

	except asyncpg.ForeignKeyViolationError:
		localizer.assign_response_error(response, "ROLE_NOT_FOUND")
		response.set_status(404)

	except Exception as e:
		pavao.Logger.error(f"Internal error giving role access: {e}")
		localizer.assign_response_error(response, "UNEXPECTED_ERROR")
		response.set_status(500)


async def pavao_endpoint(db_connection, persisted_settings):
	package_name, func_name = await localize_functionality("SET_ACCESSES",
		db_connection, persisted_settings)

	return {
		'method': 'PUT',
		'path': '/admin/roles/{roleId:int}/access/{functionalityId:int}',
		'package': package_name,
		'functionality': func_name,
		'processor': process
	}

