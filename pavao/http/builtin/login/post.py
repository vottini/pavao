
import asyncio
import argon2
import pavao

input_blueprint = pavao.include('input.jbp')
output_blueprint = pavao.include('output.jbp')
select_auth_from_login = pavao.include('select_auth_from_login.sql')
update_auth = pavao.include('update_auth.sql')

localized_messages = pavao.include('messages.ini')
localization = pavao.Localization(localized_messages)

@pavao.generatesJson(string=output_blueprint)
@pavao.acceptsJson(string=input_blueprint)
async def process(request, response, db_connection, parsed_json):
	localizer = localization.create_localizer(request)

	login = parsed_json['login']
	row = await db_connection.fetchrow(
		select_auth_from_login,
		login)

	if None == row:
		await asyncio.sleep(3)
		response.set_status(401)
		return {"error": localizer.get_message("INVALID_CREDENTIALS")}

	authId, active, storedPassword, needsChange = row

	if not active:
		response.set_status(401)
		return {"error": localizer.get_message("DISABLED_USER")}

	try:
		hasher = argon2.PasswordHasher()
		sentPassword = parsed_json['password']
		hasher.verify(storedPassword, sentPassword)

	except argon2.exceptions.VerifyMismatchError:
		await asyncio.sleep(3)
		response.set_status(401)
		return {"error": localizer.get_message("INVALID_CREDENTIALS")}

	except Exception as e:
		msg = f"Error authenticating user '{login}': {e}"
		pavao.Logger.error(msg)
		response.set_status(500)
		return {"error": localizer.get_message("INTERNAL_ERROR")}

	renewedHash = storedPassword
	if hasher.check_needs_rehash(storedPassword):
		renewedHash = hasher.hash(sentPassword)

	await db_connection.execute(update_auth, authId, renewedHash)
	return {"message": "Autorizado!"}


def pavao_endpoint():
	return {
		'method': 'POST',
		'path': '/login',
		'processor': process,
		'public': True
	}

