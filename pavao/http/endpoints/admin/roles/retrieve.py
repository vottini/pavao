
import asyncio
import pavao

from admin.common import localize_functionality

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
async def process(db_connection, path_variables):
	roleId = path_variables['roleId']

	role_info = await db_connection.fetchrow(_select_role, roleId)
	role_users = await db_connection.fetch(_retrieve_role_users, roleId)
	role_funcs = await db_connection.fetch(_retrieve_role_funcs, roleId)

	result = pavao.assemble_dicts(role_info,
		functionalities=role_funcs,
		users=role_users)

	return result


async def pavao_endpoint(db_connection, parameters):
	package_name, func_name = await localize_functionality("VIEW_ROLE",
		db_connection, parameters)

	return {
		'method': 'GET',
		'path': '/admin/roles/{roleId:int}',
		'package': package_name,
		'functionality': func_name,
		'processor': process
	}

