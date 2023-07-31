
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
		pavao.authentication (
			account,
			hash,
			active,
			needs_change,
			last_login)

		VALUES (
			$1,
			$2,
			TRUE,
			FALSE,
			CURRENT_TIMESTAMP);

"""

user_blueprint = """

	root {
		login: string(minLength=5),
		password: string(minLength=8),
		first_name: string(minLength=1),
		optional last_name: string(minLength=1)
	}

"""

user_id = "root integer"
localized_messages = pavao.include('messages.ini')
localization = pavao.Localization(localized_messages)

@pavao.generatesJson(string=user_id)
@pavao.acceptsJson(string=user_blueprint)
async def process(request, response, parsed_json, db_connection):
	hashedPassword = argon2.PasswordHasher().hash(parsed_json['password'])
	localizer = localization.create_localizer(request)

	user_args = (
		parsed_json['login'].lower(),
		capitalize(parsed_json['first_name']),
		capitalize(parsed_json.get('last_name'))
	)

	try:
		async with db_connection.transaction():
			userId = await db_connection.fetchval(add_user, *user_args)
			await db_connection.execute(add_authentication, userId, hashedPassword)

	except asyncpg.UniqueViolationError as e:
		response.set_status(409)
		return {"error": localizer.get_message("LOGIN_EXISTS")}

	except asyncpg.PostgresError as e:
		msg = f"Error creating user: {e}"
		pavao.Logger.error(msg)

		response.set_status(500)
		return {"error": localizer.get_message("UNEXPECTED_ERROR")}

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

