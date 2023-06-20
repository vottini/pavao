
import asyncio
import argon2
import time
import pavao

input_blueprint = pavao.include('input.jbp')
output_blueprint = pavao.include('output.jbp')
select_auth_from_login = pavao.include('select_auth_from_login.sql')
update_auth = pavao.include('update_auth.sql')

localized_messages = pavao.include('messages.ini')
localization = pavao.Localization(localized_messages)

#-------------------------------------------------------------------------------

_token_schema = {
	"issuer": str,
	"access_validity_min": 10,
	"refresh_validity_min": 360
}

token_settings = None
async def setup(settings, db_connection):
	global token_settings

	token_settings = settings.getSetting(
		"pavao.token",
		_token_schema)


def create_claims(subject):
	now = int(time.time())
	expiration = now + 60 * token_settings['access_validity_min']

	return {
		"iss": token_settings['issuer'],
		"sub": subject,
		"exp": expiration,
		"iat": now
	}

#-------------------------------------------------------------------------------

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

	updatedHash = storedPassword
	if hasher.check_needs_rehash(storedPassword):
		updatedHash = hasher.hash(sentPassword)

	await db_connection.execute(update_auth, authId, updatedHash)
	claims = create_claims(login)

	return {
		"change_password": needsChange,
		"token": pavao.http.generateToken(claims),
	}


def pavao_endpoint():
	return {
		'method': 'POST',
		'path': '/login',
		'processor': process,
		'init': setup,
		'public': True
	}

