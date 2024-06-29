
import asyncio
import asyncpg
import argon2
import pavao

from admin.common import localizer
from admin.common import create_message_localizer
from admin.common import assert_admin_access

update_authentication = """

	UPDATE pavao.authentication SET
		hash = $2,
		needs_change = $3
		WHERE account = $1
		RETURNING account;

"""

changes_blueprint = """

	root {
		password: string(minLength=8),
		optional changePassword: bool
	}

"""

@pavao.accepts_json(string_blueprint=changes_blueprint)
async def process(request, response, db_connection, parsed_json, path_variables):
	localizer = create_message_localizer(request)

	user_id = path_variables['user']
	hashed_password = argon2.PasswordHasher().hash(parsed_json.password)
	change_afterwards = (pavao.has_optional_field(parsed_json, 'changePassword')
		and parsed_json.changePassword)

	try:
		found_account = await db_connection.fetchval(update_authentication,
			user_id, hashed_password, change_afterwards)

		if found_account is None:
			localizer.assign_response_error(response, "USER_NOT_FOUND")
			response.set_status(404)
			return

	except asyncpg.PostgresError as e:
		pavao.Logger.error(f"Error changing password: {e}")
		localizer.assign_response_error(response, "UNEXPECTED_ERROR")
		response.set_status(500)


@assert_admin_access
def pavao_endpoint():

	return {
		'method': 'POST',
		'path': '/admin/users/{user:int}/change-password',
		'package': localizer.map("PACKAGE"),
		'functionality': localizer.map("EDIT_USERS"),
		'processor': process
	}

