
import asyncio
import pavao

from admin.common import localize_functionality

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

_retrieve_user_roles = """

	SELECT
		rl.id, rl.name, rl.admin

	FROM pavao.account acc
		INNER JOIN pavao.assignment assig ON assig.account = acc.id 
		INNER JOIN pavao."role" rl ON assig."role" = rl.id
		WHERE acc.id = $1;

"""

_user_info_blueprint = """

	root {
		login: string,
		firstName: string,
		optional lastName: string,
		creation: instant,
		lastLogin: nullable instant,
		active: bool,
		admin: bool,

		roles: {
			id: integer,
			name: string
		} []
	}

"""

@pavao.generates_json(string_blueprint=_user_info_blueprint)
async def process(db_connection, path_variables):
	infos = await db_connection.fetchrow(_select_user,
		path_variables['userId'])

	result = {
		"login": infos["login"],
		"firstName": infos["first_name"],
		"active": infos["active"],
		"creation": infos["creation"],
		"lastLogin": infos["last_login"]
	}

	lastName = infos['last_name']
	if lastName is not None:
		result['lastName'] = lastName

	roles = await db_connection.fetch(_retrieve_user_roles,
		path_variables['userId'])

	isAdmin = False
	collectedRoles = list()

	for role in roles:
		if role['admin']:
			isAdmin = True
			continue

		collectedRoles.append({
			"id": role['id'],
			"name": role['name']
		})

	result["admin"] = isAdmin
	result["roles"] = collectedRoles
	return result


async def pavao_endpoint(db_connection, parameters):
	package_name, func_name = await localize_functionality("VIEW_USER",
		db_connection, parameters)

	return {
		'method': 'GET',
		'path': '/admin/users/{userId:int}',
		'package': package_name,
		'functionality': func_name,
		'processor': process
	}

