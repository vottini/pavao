
import asyncio
import pavao

from admin.common import localize_functionality
from admin.common import create_message_localizer

retrieve_user_data = """

	SELECT
		first_name,
		last_name

		FROM pavao.account
		WHERE id = $1;

"""


list_assignments = """

	SELECT
		rl.id,
		rl.name,
		assign.account IS NOT NULL AS assigned

		FROM pavao."role" rl
			LEFT JOIN pavao.assignment assign ON
				assign."role" = rl.id AND
				assign.account = $1

		WHERE NOT rl.admin;

"""

assignments_blueprint = """

	root {
		firstName: string,
		optional lastName: string,

		assignments: {
			id: integer,
			name: string,
			assigned: bool
		} []
	}

"""

@pavao.generates_json(string_blueprint=assignments_blueprint)
async def process(request, response, db_connection, path_variables):
	userId = path_variables['user']

	user_data = await db_connection.fetchrow(
		retrieve_user_data,
		userId)

	if user_data is None:
		localizer.assign_response_error(response, "USER_NOT_FOUND")
		response.set_status(404)
		return

	assignments = await db_connection.fetch(list_assignments, userId)
	return pavao.assemble_dicts(user_data, assignments=assignments)


async def pavao_endpoint(db_connection, persisted_settings):
	package_name, func_name = await localize_functionality("LIST_ASSIGNMENTS",
		db_connection, persisted_settings)

	return {
		'method': 'GET',
		'path': '/admin/users/{user:int}/assignments',
		'package': package_name,
		'functionality': func_name,
		'processor': process
	}

