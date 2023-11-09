
import asyncio
import pavao

_select_user = """

	SELECT first_name, last_name
		FROM pavao.account
		WHERE id = $1;

"""

_user_info_blueprint = """

	root {
		firstName: string,
		optional lastName: string
	}

"""

@pavao.generatesJson(stringBlueprint=_user_info_blueprint)
async def process(db_connection, auth_data):
	retrieved = await db_connection.fetchrow(_select_user, auth_data.account_id)
	return pavao.assemble_dicts(retrieved)


def pavao_endpoint():

	return {
		'method': 'GET',
		'path': '/self',
		'processor': process
	}

