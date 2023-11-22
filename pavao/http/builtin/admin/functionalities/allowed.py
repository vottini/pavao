
import asyncio
import pavao

from admin.common import localize_functionality

select_functionalities_by_roles = """

	SELECT
		func.package AS package,
		func."name" AS functionality,
		rl."name" AS "allowing_role"
		
		FROM pavao."access" acs
			INNER JOIN pavao.functionality func ON func.id = acs.functionality 
			INNER JOIN pavao."role" rl ON acs."role" = rl.id

		WHERE rl.id = ANY($1::INTEGER[])
		ORDER BY func.package;

"""

functionalities_blueprint = """

	root {
		package: string,
		functionality: string,
		allowingRole: string
	} []

"""

@pavao.generatesJson(stringBlueprint=functionalities_blueprint)
async def process(request, response, db_connection):
	if not 'roles' in request.params:
		response.set_status(400)
		return

	try:
		raw_roles = request.params['roles']
		roles = [ int(role) for role in raw_roles.split(',') ]

	except Exception as e:
		response.set_status(400)
		print(e)
		return

	retrieved = await db_connection.fetch(
		select_functionalities_by_roles,
		roles)

	return [ pavao.assemble_dicts(row) for row in retrieved ]


async def pavao_endpoint(db_connection, parameters):
	package_name, func_name = await localize_functionality("LIST_FUNCTIONALITIES",
		db_connection, parameters)

	return {
		'method': 'GET',
		'path': '/admin/functionalities/allowed',
		'package': package_name,
		'functionality': func_name,
		'processor': process
	}

