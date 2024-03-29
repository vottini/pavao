
import asyncio
from datetime import datetime, timezone
import hashlib

import pavao
import auth.credentials as credentials

find_refresh = pavao.include('queries/find_refresh.sql')
select_roles_for_user = pavao.include('queries/select_roles_for_user.sql')
remove_refresh = pavao.include('queries/remove_refresh.sql')
insert_refresh = pavao.include('queries/insert_refresh.sql')

blueprints = pavao.path_to('blueprints.jbp')
internationalization = pavao.Internationalization(
	pavao.path_to('messages')
)

#-------------------------------------------------------------------------------

@pavao.generates_json(file_blueprint=blueprints, with_root="tokenInfo")
async def process(request, response, db_connection):
	localizer = internationalization.create_localizer(request)
	token = request.cookies.get('token')

	if token is None:
		response.set_status(400)
		return localizer.create_error(
			"MISSING_TOKEN"
		)

	refresh_claims = pavao.validate_token(token)

	if refresh_claims is None:
		response.set_status(400)
		return localizer.create_error(
			"INVALID_TOKEN"
		)

	refresh_hash = hashlib.md5(
		refresh_claims['jti'].encode()
	).digest().hex()

	account_id = refresh_claims['sub']
	found_refresh = await db_connection.fetchrow(
		find_refresh, account_id,
		refresh_hash)

	if found_refresh is None:
		response.set_status(400)
		return localizer.create_error(
			"INVALID_TOKEN"
		)

	now = datetime.now(timezone.utc)
	if found_refresh['expiration'] < now:
		response.set_status(400)
		return localizer.create_error(
			"INVALID_TOKEN"
		)

	access_claims = credentials.create_claims(account_id, now,
		credentials.access_validity)

	roles = await db_connection.fetch(
		select_roles_for_user,
		account_id)

	roles_ids = [ str(role['id']) for role in roles ]
	access_claims['roles'] = ",".join(roles_ids)
	refresh_claims = credentials.create_claims(account_id, now,
		credentials.refresh_validity)

	refresh_hash = hashlib.md5(refresh_claims['jti'].encode()).digest().hex()
	refresh_expiry = datetime.utcfromtimestamp(refresh_claims['exp'])

	async with db_connection.transaction():
		await db_connection.execute(remove_refresh, found_refresh['id'])
		await db_connection.execute(insert_refresh, account_id, refresh_hash,
			refresh_expiry, access_claims['jti'])

	access_token = pavao.generate_token(access_claims)
	refresh_token = pavao.generate_token(refresh_claims)

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

def pavao_endpoint():
	return {
		'method': 'GET',
		'path': '/refresh-token',
		'processor': process,
		'public': True
	}

