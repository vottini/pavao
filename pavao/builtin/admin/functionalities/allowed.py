
import asyncio
import pavao

from admin.common import localizer
from admin.common import assert_admin_access

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
async def process(parameters, response, request, db_connection, server):
	authorizer = server.authorizer
	retrieved = await db_connection.fetch(
		select_functionalities_by_roles,
		parameters['roles'])

	translated = [{
		"allowing_role": entry["allowing_role"],
		"package": authorizer.get_package_translation(entry['package'], request),
		"functionality": authorizer.get_func_translation(
			entry['package'], entry['functionality'],
			request)
		}

		for entry in retrieved
	]

	return [
		pavao.assemble_dicts(row)
		for row in translated
	]


@assert_admin_access
def pavao_endpoint():

	return {
		'method': 'GET',
		'path': '/admin/functionalities/allowed',
		'package': localizer.map("PACKAGE"),
		'functionality': localizer.map("LIST_FUNCTIONALITIES"),
		'processor': process
	}

