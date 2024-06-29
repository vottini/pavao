
import asyncio
import pavao

from admin.common import localizer
from admin.common import create_message_localizer
from admin.common import assert_admin_access

retrieve_role_name = """

	SELECT name FROM pavao."role"
		WHERE id = $1;

"""


list_role_accesses = """

	WITH role_access AS (
		SELECT acs.functionality, acs."role"
			FROM pavao."access" acs
				INNER JOIN pavao."role" rl ON acs."role" = rl.id
				WHERE rl.id = $1
	)

	SELECT
		func.id,
		COALESCE(func.package, '') AS package,
		func.name AS functionality,
		racs."role" IS NOT NULL AS accessable

		FROM pavao.functionality func
			LEFT JOIN role_access racs ON racs.functionality = func.id;

"""

accesses_blueprint = """

	root {
		roleName: string,
		accesses: {
			package: string,
			functionalities: {
				id: integer,
				functionality: string,
				accessable: bool
			} []
		} []
	}

"""

@pavao.generates_json(string_blueprint=accesses_blueprint)
async def process(request, response, db_connection, path_variables, server):
	role_id = path_variables['role']
	authorizer = server.authorizer

	async with db_connection.transaction():
		role_name = await db_connection.fetchval(
			retrieve_role_name,
			role_id)

		if role_name is None:
			message_localizer = create_message_localizer(request)
			message_localizer.assign_response_error(response, "ROLE_NOT_FOUND")
			response.set_status(404)
			return

		accesses = await db_connection.fetch(
			list_role_accesses,
			role_id)

	grouped = dict()
	for functionality in accesses:
		package_code = functionality['package']
		package = authorizer.get_package_translation(package_code, request)
		package_funcs = grouped.get(package, list())

		specs = dict(functionality)
		specs["functionality"] = authorizer.get_func_translation(
			package_code, functionality['functionality'],
			request)

		package_funcs.append(specs)
		grouped[package] = package_funcs

	return {
		"roleName": role_name,
		"accesses": [{'package': package, 'functionalities': funcs}
			for package, funcs in grouped.items()
		]
	}


@assert_admin_access
def pavao_endpoint():

	return {
		'method': 'GET',
		'path': '/admin/roles/{role:int}/accesses',
		'package': localizer.map("PACKAGE"),
		'functionality': localizer.map("LIST_ACCESSES"),
		'processor': process
	}

