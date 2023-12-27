
import asyncio
import pavao

from admin.common import localize_functionality
from admin.common import create_message_localizer

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
async def process(request, db_connection, path_variables):
	user_id = path_variables['user']

	infos = await db_connection.fetchrow(
		_select_user,
		user_id)

	if infos is None:
		localizer = create_message_localizer(request)
		localizer.assign_response_error(response, "USER_NOT_FOUND")
		response.set_status(404)
		return

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

	roles = await db_connection.fetch(
		_retrieve_user_roles,
		user_id)

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


async def pavao_endpoint(db_connection, persisted_settings):
	package_name, func_name = await localize_functionality("VIEW_USER",
		db_connection, persisted_settings)

	return {
		'method': 'GET',
		'path': '/admin/users/{user:int}',
		'package': package_name,
		'functionality': func_name,
		'processor': process
	}

