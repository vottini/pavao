
import asyncio
import pavao

list_functionalities = """

	SELECT COALESCE(package, ''), id, name, enabled
		FROM pavao.functionality;

"""

functionalities_list = """

	root {
		package: string,
		functionalities: {
			id: integer,
			functionality: string,
			enabled: bool
		} []
	} []

"""

@pavao.generatesJson(stringBlueprint=functionalities_list)
async def process(request, response, db_connection):
	functionalities = await db_connection.fetch(list_functionalities)
	grouped = dict()

	for package, func_id, functionality, enabled in functionalities:
		pack = grouped.get(package, list())

		pack.append({
			'id': func_id,
			'functionality': functionality,
			'enabled': enabled
		})

		grouped[package] = pack

	result = [
		{ 'package': package, 'functionalities': funcs }
		for package, funcs in grouped.items()
	]

	return result


from admin.common import localize_functionality
async def pavao_endpoint(db_connection, parameters):
	func_name = await localize_functionality("LIST_FUNCTIONALITIES",
		db_connection, parameters)

	return {
		'method': 'GET',
		'path': '/admin/functionalities',
		'functionality': func_name,
		'processor': process
	}

