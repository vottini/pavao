
import asyncio
import pavao

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

@pavao.generates_json(string_blueprint=functionalities_blueprint)
@pavao.accepts_parameters({'roles': [int]})
async def process(parameters, response, db_connection):
	retrieved = await db_connection.fetch(
		select_functionalities_by_roles,
		parameters['roles'])

	return [
		pavao.assemble_dicts(row)
		for row in retrieved
	]


from admin.common import localize_functionality
async def pavao_endpoint(db_connection, persisted_settings):
	package_name, func_name = await localize_functionality("LIST_FUNCTIONALITIES",
		db_connection, persisted_settings)

	return {
		'method': 'GET',
		'path': '/admin/functionalities/allowed',
		'package': package_name,
		'functionality': func_name,
		'processor': process
	}

