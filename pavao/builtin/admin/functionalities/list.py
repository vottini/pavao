
import asyncio
import pavao

from admin.common import localizer
from admin.common import assert_admin_access

list_functionalities = """

	SELECT
		id,
		COALESCE(package, '') AS package,
		name AS functionality,
		enabled,
		active

		FROM pavao.functionality;

"""

functionalities_list = """

	root {
		package: nullable string,
		functionalities: {
			id: integer,
			functionality: string,
			enabled: bool,
			active: bool
		} []
	} []

"""

@pavao.generates_json(string_blueprint=functionalities_list)
async def process(request, db_connection, server):
	functionalities = await db_connection.fetch(list_functionalities)
	authorizer = server.authorizer

	grouped = dict()
	for functionality in functionalities:
		package_code = functionality['package']
		package = authorizer.get_package_translation(package_code, request)
		package_funcs = grouped.get(package, list())

		specs = dict(functionality)
		specs["functionality"] = authorizer.get_func_translation(
			package_code, functionality['functionality'],
			request)

		package_funcs.append(specs)
		grouped[package] = package_funcs

	return [
		{'package': package, 'functionalities': funcs}
		for package, funcs in grouped.items()
	]


@assert_admin_access
def pavao_endpoint():

	return {
		'method': 'GET',
		'path': '/admin/functionalities',
		'package': localizer.map("PACKAGE"),
		'functionality': localizer.map("LIST_FUNCTIONALITIES"),
		'processor': process
	}

