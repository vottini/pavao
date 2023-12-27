
import asyncio
import pavao

from admin.common import localize_functionality
from admin.common import create_message_localizer

_select_role = """

	SELECT name, description
		FROM pavao."role"
		WHERE id = $1;

"""

_retrieve_role_users = """

	SELECT acc.id, CONCAT_WS(' ', acc.first_name, acc.last_name) AS full_name FROM
		pavao."role" rl
			INNER JOIN pavao."assignment" assig ON assig."role" = rl.id
			INNER JOIN pavao.account acc ON assig.account = acc.id
			WHERE rl.id = $1 AND acc.active;

"""

_retrieve_role_funcs = """

	SELECT func.id, func.name, func.package from
		pavao."role" rl
			INNER JOIN pavao.access acs ON acs."role" = rl.id
			INNER JOIN pavao.functionality func ON acs.functionality = func.id
			WHERE func.enabled AND rl.id = $1;

"""

_role_info_blueprint = """

	root {
		name: string,
		optional description: string,

		users: {
			id: integer,
			fullName: string
		} [],

		functionalities: {
			id: integer,
			name: string,
			optional package: string
		} []
	}

"""

@pavao.generates_json(string_blueprint=_role_info_blueprint)
async def process(request, response, db_connection, path_variables):
	role_id = path_variables['role']

	async with db_connection.transaction():
		role_info = await db_connection.fetchrow(_select_role, role_id)

		if role_info is None:
			localizer = create_message_localizer(request)
			localizer.assign_response_error(response, "ROLE_NOT_FOUND")
			response.set_status(404)
			return None

		role_users = await db_connection.fetch(_retrieve_role_users, role_id)
		role_funcs = await db_connection.fetch(_retrieve_role_funcs, role_id)

	return pavao.assemble_dicts(role_info,
		functionalities=role_funcs,
		users=role_users)


async def pavao_endpoint(db_connection, persisted_settings):
	package_name, func_name = await localize_functionality("VIEW_ROLE",
		db_connection, persisted_settings)

	return {
		'method': 'GET',
		'path': '/admin/roles/{role:int}',
		'package': package_name,
		'functionality': func_name,
		'processor': process
	}

