
import asyncio
import pavao

from admin.common import localizer
from admin.common import create_message_localizer
from admin.common import assert_admin_access

select_role = """

	SELECT
		name,
		description

		FROM pavao."role"
		WHERE id = $1;

"""

retrieve_role_users = """

	SELECT
		acc.id,
		CONCAT_WS(' ', acc.first_name, acc.last_name) AS full_name

		FROM pavao."role" rl
			INNER JOIN pavao."assignment" assig ON assig."role" = rl.id
			INNER JOIN pavao.account acc ON assig.account = acc.id
			WHERE rl.id = $1 AND acc.active;

"""

retrieve_role_funcs = """

	SELECT
		func.id,
		func.name,
		func.package

		from pavao."role" rl
			INNER JOIN pavao.access acs ON acs."role" = rl.id
			INNER JOIN pavao.functionality func ON acs.functionality = func.id
			WHERE func.enabled AND rl.id = $1;

"""

role_info_blueprint = """

	root {
		name: string,
		description: nullable string,

		users: {
			id: integer,
			fullName: string
		} [],

		functionalities: {
			id: integer,
			name: string,
			package: nullable string
		} []
	}

"""


@pavao.generates_json(string_blueprint=role_info_blueprint)
async def process(request, response, db_connection, path_variables, server):
	role_id = path_variables['role']
	auther = server.authorizer

	async with db_connection.transaction():
		role_info = await db_connection.fetchrow(
			select_role, role_id)

		if role_info is None:
			message_localizer = create_message_localizer(request)
			message_localizer.assign_response_error(response, "ROLE_NOT_FOUND")
			response.set_status(404)
			return None

		role_users = await db_connection.fetch(retrieve_role_users, role_id)
		role_funcs = await db_connection.fetch(retrieve_role_funcs, role_id)

		translated_role_funcs = list()
		for functionality in role_funcs:
			specs = dict(functionality)

			package_code = functionality['package']
			specs['package'] = auther.get_package_translation(package_code, request)
			specs["name"] = auther.get_func_translation(package_code,
				specs['name'], request)

			translated_role_funcs.append(specs)

	return pavao.assemble_dicts(role_info,
		functionalities=translated_role_funcs,
		users=role_users)


@assert_admin_access
def pavao_endpoint():

	return {
		'method': 'GET',
		'path': '/admin/roles/{role:int}',
		'package': localizer.map("PACKAGE"),
		'functionality': localizer.map("VIEW_ROLE"),
		'processor': process
	}

