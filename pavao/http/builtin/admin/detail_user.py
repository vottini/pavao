
import asyncio
import pavao

_select_user = """

	SELECT
		login,
		first_name,
		last_name,
		active,
		creation,
		last_login

	FROM pavao.account
	WHERE id = $1;

"""

_user_info_blueprint = """

	root {
		login: string,
		firstName: string,
		optional lastName: string
	}

"""

@pavao.generatesJson(stringBlueprint=_user_info_blueprint)
async def process(db_connection, path_variables):
	retrieved = await db_connection.fetchrow(_select_user,
		path_variables['userId'])

	result = {
		"login": retrieved["login"],
		"firstName": retrieved["first_name"]
	}

	lastName = retrieved['last_name']
	if lastName is not None:
		result['lastName'] = lastName

	return result


async def pavao_endpoint():
	return {
		'method': 'GET',
		'path': '/admin/users/{userId:int}',
		'processor': process
	}

