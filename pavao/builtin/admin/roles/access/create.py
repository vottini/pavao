
import asyncio
import asyncpg
import pavao

from admin.common import localizer
from admin.common import create_message_localizer
from admin.common import assert_admin_access

allow_query = """

	INSERT INTO pavao."access" (functionality, "role")
		VALUES ($1, $2)

"""

async def process(request, response, db_connection, path_variables, server):
	message_localizer = create_message_localizer(request)

	try:
		await db_connection.execute(allow_query,
			path_variables['functionality'],
			path_variables['role'])

		authorizer = server.authorizer
		await authorizer.allow_access(db_connection,
			path_variables['functionality'],
			path_variables['role'])

	except asyncpg.ForeignKeyViolationError:
		message_localizer.assign_response_error(response, "ROLE_NOT_FOUND")
		response.set_status(404)

	except Exception as e:
		pavao.Logger.error(f"Internal error giving role access: {e}")
		message_localizer.assign_response_error(response, "UNEXPECTED_ERROR")
		response.set_status(500)


@assert_admin_access
def pavao_endpoint():

	return {
		'method': 'PUT',
		'path': '/admin/roles/{role:int}/access/{functionality:int}',
		'package': localizer.map("PACKAGE"),
		'functionality': localizer.map("SET_ACCESSES"),
		'processor': process
	}

