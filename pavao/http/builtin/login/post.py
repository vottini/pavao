
import asyncio
import asyncpg
import argon2
import pavao

login_blueprint = pavao.include('login.jbp')
select_auth_from_login = pavao.include('select_auth_from_login.sql')
update_auth = pavao.include('update_auth.sql')

#@pavao.generatesJson
@pavao.acceptsJson(string=login_blueprint)
async def process(response, db_connection, parsed_json):
	login = parsed_json['login']

	row = await db_connection.fetchrow(
		select_auth_from_login,
		login)

	if None == row:
		response.set_plain_text("Invalid Credentials")
		response.set_status(403)
		await asyncio.sleep(3)
		return

	authId, active, storedPassword, needsChange = row

	if not active:
		response.set_plain_text("User is not active")
		response.set_status(403)
		return

	try:
		hasher = argon2.PasswordHasher()
		sentPassword = parsed_json['password']
		hasher.verify(storedPassword, sentPassword)

	except argon2.exceptions.VerifyMismatchError:
		response.set_plain_text("Invalid Credentials")
		response.set_status(403)
		await asyncio.sleep(3)
		return

	except Exception as e:
		response.set_plain_text("Error verifying credentials")
		response.set_status(500)
		return

	renewedHash = storedPassword
	if hasher.check_needs_rehash(storedPassword):
		renewedHash = hasher.hash(sentPassword)

	await db_connection.execute(update_auth, authId, renewedHash)
	response.set_plain_text(f"Autorizado!")


def pavao_endpoint():
	return {
		'method': 'POST',
		'path': '/login',
		'processor': process,
		'public': True
	}

