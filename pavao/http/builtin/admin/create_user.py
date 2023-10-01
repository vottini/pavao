
import asyncio
import asyncpg
import argon2
import pavao

from admin.common import localize_functionality, capitalize

add_user = """

	INSERT INTO
		pavao.account (login, first_name, last_name)
		VALUES ($1, $2, $3)
		RETURNING id;

"""

add_authentication = """

	INSERT INTO
		pavao.authentication (account, hash, needs_change)
		VALUES ($1, $2, FALSE);

"""

credentials_blueprint = """

	root {
		login: string(minLength=5, format="^[a-z][a-z0-9]*(?:.[a-z0-9]+)?$"),
		password: string(minLength=8),
		firstName: string(minLength=1),
		optional lastName: string(minLength=1)
	}

"""

user_id = "root integer"
localized_messages = pavao.include('messages.ini')
localization = pavao.Localization(localized_messages)

@pavao.generatesJson(stringBlueprint=user_id)
@pavao.acceptsJson(stringBlueprint=credentials_blueprint)
async def process(request, response, db_connection, parsed_json):
	hashedPassword = argon2.PasswordHasher().hash(parsed_json.password)
	localizer = localization.create_localizer(request)

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
			await db_connection.execute(add_authentication, userId, hashedPassword)

	except asyncpg.UniqueViolationError as e:
		response.set_status(409)
		return localizer.create_message("LOGIN_EXISTS")

	except asyncpg.PostgresError as e:
		pavao.Logger.error(f"Error creating user: {e}")
		response.set_status(500)

		return localizer.create_message("UNEXPECTED_ERROR")

	response.set_status(201)
	return userId


async def pavao_endpoint(db_connection, parameters):
	func_name = await localize_functionality("CREATE_USERS",
		db_connection, parameters)

	return {
		'method': 'POST',
		'path': '/admin/users',
		'functionality': func_name,
		'processor': process
	}

