
import asyncio
import argon2
import pavao

from access.registering import localize_functionality

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

@pavao.acceptsJson(string=user_blueprint)
async def process(parsed_json, response, db_connection):
	hashedPassword = argon2.PasswordHasher().hash(parsed_json['password'])

	user_args = (
		parsed_json['login'],
		parsed_json['first_name'],
		parsed_json.get('last_name'))

	async with db_connection.transaction():
		userId = await db_connection.fetchval(add_user, *user_args)
		await db_connection.execute(add_authentication, userId, hashedPassword)

	response.set_status(201)


async def pavao_endpoint(db_connection, parameters):
	func_name = await localize_functionality("CREATE_USERS",
		db_connection, parameters)

	return {
		'method': 'POST',
		'path': '/access/users',
		'functionality': func_name,
		'processor': process
	}

