
import asyncio
import pavao

from access.registering import localize_functionality
list_users = "SELECT login, first_name, last_name FROM pavao.account;"

user_blueprint = """

  root {
    login: string,
    firstName: string,
    optional lastName: string
  } []

"""

def mapUser(userData):

	result = {
		"login": userData['login'],
		"firstName": userData['first_name']
	}

	lastName = userData['last_name']
	if lastName is not None:
		result['lastName'] = lastName

	return result


@pavao.generatesJson(string=user_blueprint)
async def process(request, response, db_connection):
	result = await db_connection.fetch(list_users)
	return [ mapUser(row) for row in result ]


async def pavao_endpoint(db_connection, parameters):
	func_name = await localize_functionality("LIST_USERS",
		db_connection, parameters)

	return {
		'method': 'GET',
		'path': '/access/users',
		'functionality': func_name,
		'processor': process
	}

