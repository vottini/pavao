
import asyncio
import pavao

from admin.common import localize_functionality

list_admins = """

  SELECT acc.id, acc.first_name, acc.last_name, acc.login = $1 AS my_account
    FROM pavao.assignment assig
      INNER JOIN pavao.account acc ON assig.account = acc.id
      INNER JOIN pavao."role" rl ON assig."role" = rl.id 
    WHERE rl.admin;

"""

user_blueprint = """

  root {
    id: integer,
    firstName: string,
    optional lastName: string,
    myAccount: bool
  } []

"""

def mapUser(userData):

	result = {
		"id": userData['id'],
		"firstName": userData['first_name'],
		"myAccount": userData['my_account']
	}

	lastName = userData['last_name']
	if lastName is not None:
		result['lastName'] = lastName

	return result


@pavao.generatesJson(stringBlueprint=user_blueprint)
async def process(request, response, auth_data, db_connection):
	result = await db_connection.fetch(list_admins, auth_data.login)
	return [ mapUser(row) for row in result ]


async def pavao_endpoint(db_connection, parameters):
	package_name, func_name = await localize_functionality("LIST_ADMINS",
		db_connection, parameters)

	return {
		'method': 'GET',
		'path': '/admin/admins',
		'package': package_name,
		'functionality': func_name,
		'processor': process
	}

