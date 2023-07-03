
import asyncio
import argon2
import secrets
from datetime import datetime, timedelta, timezone
import hashlib
import pavao

input_blueprint = pavao.include('input.jbp')
output_blueprint = pavao.include('output.jbp')

insert_refresh = pavao.include('insert_refresh.sql')
select_auth_from_login = pavao.include('select_auth_from_login.sql')
select_classes_from_login = pavao.include('select_classes_from_login.sql')
update_auth = pavao.include('update_auth.sql')

localized_messages = pavao.include('messages.ini')
localization = pavao.Localization(localized_messages)

#-------------------------------------------------------------------------------

_token_schema = {
	"issuer": str,
	"validity": {
		"access_minutes": 10,
		"refresh_minutes": 360
	}
}

token_settings = None
async def setup(settings, db_connection):
	global token_settings

	token_settings = settings.getSetting(
		"pavao.token",
		_token_schema)

access_validity = 'access_minutes'
refresh_validity = 'refresh_minutes'

def create_claims(subject, issue_time, minutes_validity):
	validities = token_settings['validity']
	expiration = issue_time + timedelta(minutes=validities[minutes_validity])
	issuer = token_settings['issuer']

	return {
		"iss": issuer,
		"sub": subject,
		"aud": issuer,
		"exp": int(expiration.timestamp()),
		"nbf": int(issue_time.timestamp()),
		"iat": int(issue_time.timestamp()),
		"jti": secrets.token_urlsafe(32)
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

	authId, active, storedPassword, changePassword = row

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

	now = datetime.now(timezone.utc)
	access_claims = create_claims(login, now, access_validity)
	access_expiry = access_claims['exp']

	if changePassword:
		access_claims['cls'] = ""
		access_token = pavao.http.generateToken(access_claims)

		return {
			"token": access_token,
			"change_password": True,
			"expires": access_expiry
		}

	classes = await db_connection.fetch(select_classes_from_login, login)
	classes_ids = [ str(cls['id']) for cls in classes ]
	access_claims['cls'] = ",".join(classes_ids)

	refresh_claims = create_claims(login, now, refresh_validity)
	refresh_hash = hashlib.md5(refresh_claims['jti'].encode()).digest().hex()
	refresh_expiry = now + timedelta(minutes=token_settings['validity']
		[refresh_validity])

	updatedHash = storedPassword
	if hasher.check_needs_rehash(storedPassword):
		updatedHash = hasher.hash(sentPassword)

	async with db_connection.transaction():
		await db_connection.execute(update_auth, authId, updatedHash)
		await db_connection.execute(insert_refresh, login, refresh_hash,
			refresh_expiry, access_claims['jti'])

	access_token = pavao.http.generateToken(access_claims)
	refresh_token = pavao.http.generateToken(refresh_claims)

	response.add_cookie(
		pavao.http.Cookie('refresh-token', refresh_token)
			.set_sameSite(pavao.http.SameSite.STRICT)
			.set_path('/refresh')
			.set_httpOnly()
	)

	return {
		"token": access_token,
		"change_password": False,
		"expires": access_expiry
	}

#-------------------------------------------------------------------------------

def pavao_endpoint():
	return {
		'method': 'POST',
		'path': '/login',
		'processor': process,
		'init': setup,
		'public': True
	}

