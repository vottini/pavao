
import asyncio
import asyncpg
import argon2
import pavao

from admin.common import localize_functionality, capitalize
from admin.common import message_localization

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

@pavao.acceptsJson(stringBlueprint=changes_blueprint)
async def process(request, response, db_connection, parsed_json, path_variables):
	localizer = message_localization().create_localizer(request)

	user_id = path_variables['userId']
	hashed_password = argon2.PasswordHasher().hash(parsed_json.password)
	change_afterwards = (pavao.has_optional_field(parsed_json, 'changePassword')
		and parsed_json.changePassword)

	try:
		found_account = await db_connection.fetchval(update_authentication,
			user_id, hashed_password, change_afterwards)

		if found_account is None:
			response.set_status(404)
			return

	except asyncpg.PostgresError as e:
		pavao.Logger.error(f"Error changing password: {e}")

		response.set_status(500)
		return localizer.create_error(
			"UNEXPECTED_ERROR"
		)

	response.set_status(204)
	return found_account


async def pavao_endpoint(db_connection, parameters):
	package_name, func_name = await localize_functionality("CREATE_USERS",
		db_connection, parameters)

	return {
		'method': 'POST',
		'path': '/admin/users/{userId:int}/change-password',
		'package': package_name,
		'functionality': func_name,
		'processor': process
	}

