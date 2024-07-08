
import asyncio
import pavao

from admin.common import localizer
from admin.common import create_message_localizer
from admin.common import assert_admin_access

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
		lastName: nullable string,
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

	user_info = await db_connection.fetchrow(
		_select_user,
		user_id)

	if user_info is None:
		localizer = create_message_localizer(request)
		localizer.assign_response_error(response, "USER_NOT_FOUND")
		response.set_status(404)
		return

	roles = await db_connection.fetch(
		_retrieve_user_roles,
		user_id)

	admin = False
	collected_roles = list()

	for role in roles:
		if role['admin']:
			admin = True
			continue

		role_info = pavao.assemble_dicts(role)
		collected_roles.append(role_info)

	result = pavao.assemble_dicts(user_info,
		roles=collected_roles,
		admin=admin)

	return result


@assert_admin_access
def pavao_endpoint():

	return {
		'method': 'GET',
		'path': '/admin/users/{user:int}',
		'package': localizer.map("PACKAGE"),
		'functionality': localizer.map("VIEW_USER"),
		'processor': process
	}

