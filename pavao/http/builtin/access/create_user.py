
import asyncio
import pavao

from access.registering import localize_functionality
list_functionalities = "SELECT name FROM pavao.functionality;"
string_list = "root string[]"


@pavao.generatesJson(string=string_list)
async def process(request, response, db_connection):
	result = await db_connection.fetch(list_functionalities)
	return [ row[0] for row in result ]


async def pavao_endpoint(db_connection, parameters):
	func_name = await localize_functionality("CREATE_USERS",
		db_connection, parameters)

	return {
		'method': 'POST',
		'path': '/access/users',
		'functionality': func_name,
		'processor': process
	}

