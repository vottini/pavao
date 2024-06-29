
import asyncio
import asyncpg
import argon2
import pavao

from admin.common import localizer
from admin.common import create_message_localizer
from admin.common import assert_admin_access
from admin.common import capitalize

add_user = """

	INSERT INTO
		pavao.account (login, first_name, last_name)
		VALUES ($1, $2, $3)
		RETURNING id;

"""

add_authentication = """

	INSERT INTO
		pavao.authentication (account, hash, needs_change)
		VALUES ($1, $2, $3);

"""

user_info_blueprint = """

	root {
		login: string(minLength=5, format="^[a-z][a-z0-9]*(?:.[a-z0-9]+)?$"),
		password: string(minLength=8),
		firstName: string(minLength=1),
		optional lastName: string(minLength=1),
		changePassword: bool
	}

"""

@pavao.generates_json(string_blueprint="root integer")
@pavao.accepts_json(string_blueprint=user_info_blueprint)
async def process(request, response, db_connection, parsed_json):
	hashedPassword = argon2.PasswordHasher().hash(parsed_json.password)
	localizer = create_message_localizer(request)

	user_args = (
		parsed_json.login.lower(),
		capitalize(parsed_json.firstName),
		(capitalize(parsed_json.lastName)
			if pavao.has_optional_field(parsed_json, 'lastName')
			else None)
	)

	try:
		async with db_connection.transaction():
			userId = await db_connection.fetchval(add_user, *user_args)
			await db_connection.execute(add_authentication, userId,
				hashedPassword, parsed_json.changePassword)

	except asyncpg.UniqueViolationError as e:
		response.set_status(409)
		return localizer.create_message(
			"LOGIN_EXISTS"
		)

	except asyncpg.PostgresError as e:
		pavao.Logger.error(f"Error creating user: {e}")

		response.set_status(500)
		return localizer.create_message(
			"UNEXPECTED_ERROR"
		)

	response.set_status(201)
	return userId


@assert_admin_access
def pavao_endpoint():

	return {
		'method': 'POST',
		'path': '/admin/users',
		'package': localizer.map("PACKAGE"),
		'functionality': localizer.map("CREATE_USERS"),
		'processor': process
	}

