
import asyncio
import pavao

_select_user = """

	SELECT first_name, last_name
		FROM pavao.account
		WHERE id = $1;

"""

_count_admin_roles = """

	SELECT COUNT(*)
		FROM pavao."role" rl
			INNER JOIN pavao."assignment" assig ON assig."role" = rl.id 

		WHERE
			assig.account = $1 AND
			rl."admin" ;

"""

_user_info_blueprint = """

	root {
		firstName: string,
		optional lastName: string,
		administrator: bool
	}

"""

@pavao.generatesJson(stringBlueprint=_user_info_blueprint)
async def process(db_connection, auth_data):
	admin_roles = await db_connection.fetchval(_count_admin_roles, auth_data.account_id)
	retrieved = await db_connection.fetchrow(_select_user, auth_data.account_id)
	return pavao.assemble_dicts(retrieved, administrator=admin_roles > 0)


def pavao_endpoint():

	return {
		'method': 'GET',
		'path': '/self',
		'processor': process
	}

