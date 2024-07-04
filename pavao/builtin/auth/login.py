
import asyncio
import argon2
from datetime import datetime, timedelta, timezone
import hashlib

import pavao
import auth.credentials as credentials

insert_refresh = pavao.include('queries/insert_refresh.sql')
select_auth_from_login = pavao.include('queries/select_auth_from_login.sql')
select_roles_for_user = pavao.include('queries/select_roles_for_user.sql')
update_auth = pavao.include('queries/update_auth.sql')
touch_account = pavao.include('queries/touch_account.sql')

blueprints = pavao.path_to('blueprints.jbp')
internationalization = pavao.Internationalization(
	pavao.path_to('messages')
)

#-------------------------------------------------------------------------------

@pavao.generates_json(file_blueprint=blueprints, with_root="tokenInfo")
@pavao.accepts_json(file_blueprint=blueprints, with_root="credentials")
async def process(request, response, db_connection, parsed_json):
	localizer = internationalization.create_localizer(
		request.parse_locale_priority())

	row = await db_connection.fetchrow(
		select_auth_from_login,
		parsed_json.login)

	if row is None:
		await asyncio.sleep(3)
		response.set_status(401)
		return localizer.create_error(
			"INVALID_CREDENTIALS"
		)

	account_id, authId, active, storedPassword, changePassword = row

	if not active:
		await asyncio.sleep(3)
		response.set_status(401)
		return localizer.create_error(
			"DISABLED_USER"
		)

	try:
		hasher = argon2.PasswordHasher()
		sent_password = parsed_json.password
		hasher.verify(storedPassword, sent_password)

	except argon2.exceptions.VerifyMismatchError:
		await asyncio.sleep(3)
		response.set_status(401)
		return localizer.create_error(
			"INVALID_CREDENTIALS"
		)

	except Exception as e:
		error_msg = f"Error authenticating user '{parsed_json.login}': {e}"
		pavao.Logger.error(error_msg)

		response.set_status(500)
		return localizer.create_error(
			"INTERNAL_ERROR"
		)

	updatedHash = storedPassword
	if hasher.check_needs_rehash(storedPassword):
		updatedHash = hasher.hash(sent_password)
		await db_connection.execute(update_auth,
			authId, updatedHash)

	now = datetime.now(timezone.utc)
	access_claims = credentials.create_claims(account_id, now,
		credentials.access_validity)

	if changePassword:
		access_claims['roles'] = ""
		access_token = pavao.generate_token(access_claims)

		return {
			"token": access_token,
			"change_password": True,
			"expires": access_claims['exp']
		}

	roles = await db_connection.fetch(
		select_roles_for_user,
		account_id)

	roles_ids = [ str(role['id']) for role in roles ]
	access_claims['roles'] = ",".join(roles_ids)

	refresh_claims = credentials.create_claims(account_id, now,
		credentials.refresh_validity)

	refresh_hash = hashlib.md5(refresh_claims['jti'].encode()).digest().hex()
	refresh_expiry = datetime.utcfromtimestamp(refresh_claims['exp'])

	await db_connection.execute(insert_refresh,
		account_id,
		refresh_hash,
		refresh_expiry,
		access_claims['jti'])

	access_token = pavao.generate_token(access_claims)
	refresh_token = pavao.generate_token(refresh_claims)
	await db_connection.execute(touch_account,
		parsed_json.login)

	response.add_cookie(
		pavao.http.Cookie('token', refresh_token)
			.set_sameSite(pavao.http.SameSite.STRICT)
			.set_path('/refresh-token')
			.set_httpOnly()
	)

	return {
		"token": access_token,
		"change_password": False,
		"expires": access_claims['exp']
	}

#-------------------------------------------------------------------------------

async def pavao_endpoint(loaded_settings):
	await credentials.setup(loaded_settings)

	return {
		'method': 'POST',
		'path': '/login',
		'processor': process,
		'public': True
	}

