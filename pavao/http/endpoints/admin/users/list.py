
import asyncio
import pavao

from admin.common import localize_functionality

list_admins = """

	SELECT
		acc.id,
		acc.first_name,
		acc.last_name,
		acc.active,
		bool_or(COALESCE(rl."admin", FALSE)) as is_admin,
		acc.id = $1 as my_account

	FROM pavao.account acc
		LEFT JOIN pavao."assignment" assig ON assig.account = acc.id 
		LEFT JOIN pavao."role" rl ON assig."role" = rl.id

	WHERE NOT acc.managerial
	GROUP BY acc.id;

"""

user_blueprint = """

	root {
		id: integer,
		firstName: string,
		optional lastName: string,
		active: bool,
		isAdmin: bool,
		myAccount: bool
	} []

"""

@pavao.generates_json(string_blueprint=user_blueprint)
async def process(request, response, auth_data, db_connection):
	retrieved = await db_connection.fetch(list_admins, auth_data.account_id)
	return [ pavao.assemble_dicts(row) for row in retrieved ]


async def pavao_endpoint(db_connection, parameters):
	package_name, func_name = await localize_functionality("LIST_USERS",
		db_connection, parameters)

	return {
		'method': 'GET',
		'path': '/admin/users',
		'package': package_name,
		'functionality': func_name,
		'processor': process
	}

