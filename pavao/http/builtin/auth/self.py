
import asyncio
import pavao

_select_user = """

	SELECT first_name, last_name
		FROM pavao.account
		WHERE login = $1;

"""

_user_info_blueprint = """

	root {
		firstName: string,
		optional lastName: string
	}

"""

@pavao.generatesJson(stringBlueprint=_user_info_blueprint)
async def process(db_connection, auth_data):
	retrieved = await db_connection.fetchrow(_select_user,
		auth_data.login)

	result = { "firstName": retrieved["first_name"] }
	if (lastName := retrieved["last_name"]) is not None:
		result["lastName"] = lastName
	
	return result


async def pavao_endpoint():
	return {
		'method': 'GET',
		'path': '/self',
		'processor': process
	}

