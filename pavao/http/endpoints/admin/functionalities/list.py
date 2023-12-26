
import asyncio
import pavao

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
		package: string,
		functionalities: {
			id: integer,
			functionality: string,
			enabled: bool,
			active: bool
		} []
	} []

"""

@pavao.generates_json(string_blueprint=functionalities_list)
async def process(request, db_connection):
	functionalities = await db_connection.fetch(list_functionalities)

	grouped = dict()
	for functionality in functionalities:
		package = functionality['package']
		package_funcs = grouped.get(package, list())
		package_funcs.append(dict(functionality))
		grouped[package] = package_funcs

	result = [
		{
			'package': package,
			'functionalities': funcs
		}

		for package, funcs in grouped.items()
	]

	return result


from admin.common import localize_functionality
async def pavao_endpoint(db_connection, persisted_settings):
	package_name, func_name = await localize_functionality("LIST_FUNCTIONALITIES",
		db_connection, persisted_settings)

	return {
		'method': 'GET',
		'path': '/admin/functionalities',
		'package': package_name,
		'functionality': func_name,
		'processor': process
	}

