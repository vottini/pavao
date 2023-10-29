
import asyncio
import pavao

from admin.common import localize_functionality


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

@pavao.generatesJson(stringBlueprint=accesses_blueprint)
async def process(request, response, db_connection, path_variables):
	role_name = await db_connection.fetchval(retrieve_role_name,
		path_variables['roleId'])

	if role_name is None:
		response.set_status(404)
		return

	accesses = await db_connection.fetch(list_role_accesses,
		path_variables['roleId'])

	grouped = dict()
	for functionality in accesses:
		package = functionality['package']
		package_funcs = grouped.get(package, list())
		package_funcs.append(dict(functionality))
		grouped[package] = package_funcs
	
	return {
		"roleName": role_name,
		"accesses": [
			{ 'package': package, 'functionalities': funcs }
			for package, funcs in grouped.items()
		]
	}


async def pavao_endpoint(db_connection, parameters):
	package_name, func_name = await localize_functionality("LIST_ACCESSES",
		db_connection, parameters)

	return {
		'method': 'GET',
		'path': '/admin/roles/{roleId:int}/accesses',
		'package': package_name,
		'functionality': func_name,
		'processor': process
	}

