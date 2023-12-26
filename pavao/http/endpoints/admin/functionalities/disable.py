
import asyncio
import pavao

from admin.common import localize_functionality
from admin.common import create_message_localizer

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
	localizer = create_message_localizer(request)

	functionality_id = path_variables['functionality']
	admin_roles = await db_connection.fetchval(check_admin,
		functionality_id)

	if admin_roles > 0:
		localizer.assign_response_error(response, "ADMIN_FUNCTIONALITY")
		response.set_status(403)
		return

	updated_functionality = await db_connection.fetchval(
		disable_funcionality_query,
		functionality_id)

	if updated_functionality is None:
		localizer.assign_response_error(response, "FUNCTIONALITY_NOT_FOUND")
		response.set_status(404)
		return

	authorizer = handler.authorizer
	authorizer.disable_functionality(
		updated_functionality)


async def pavao_endpoint(db_connection, persisted_settings):
	package_name, func_name = await localize_functionality("MANAGE_FUNCTIONALITIES",
		db_connection, persisted_settings)

	return {
		'method': 'PUT',
		'path': '/admin/functionalities/{functionality:int}/disable',
		'package': package_name,
		'functionality': func_name,
		'processor': process
	}

