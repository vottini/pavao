
import asyncio
from datetime import datetime, timezone
import hashlib

import pavao
import auth.credentials as credentials

output_blueprint = pavao.include('output.jbp')

find_refresh = pavao.include('find_refresh.sql')
select_classes_from_login = pavao.include('select_classes_from_login.sql')
remove_refresh = pavao.include('remove_refresh.sql')
insert_refresh = pavao.include('insert_refresh.sql')

localized_messages = pavao.include('messages.ini')
localization = pavao.Localization(localized_messages)

#-------------------------------------------------------------------------------

@pavao.generatesJson(string=output_blueprint)
async def process(request, response, db_connection):
	localizer = localization.create_localizer(request)
	token = request.cookies.get('token')

	if token is None:
		response.set_status(400)
		return {"error": localizer.get_message("MISSING_TOKEN")}

	refresh_claims = pavao.validateToken(token)

	if refresh_claims is None:
		response.set_status(400)
		return {"error": localizer.get_message("INVALID_TOKEN")}
	
	login = refresh_claims['sub']
	refresh_hash = hashlib.md5(refresh_claims['jti'].encode()).digest().hex()
	found_refresh = await db_connection.fetchrow(find_refresh, login, refresh_hash)

	if found_refresh is None:
		response.set_status(400)
		return {"error": localizer.get_message("INVALID_TOKEN")}

	now = datetime.now(timezone.utc)
	if found_refresh['expiration'] < now:
		response.set_status(400)
		return {"error": localizer.get_message("INVALID_TOKEN")}

	access_claims = credentials.create_claims(login, now,
		credentials.access_validity)

	classes = await db_connection.fetch(select_classes_from_login, login)
	classes_ids = [ str(cls['id']) for cls in classes ]
	access_claims['cls'] = ",".join(classes_ids)

	refresh_claims = credentials.create_claims(login, now,
		credentials.refresh_validity)

	refresh_hash = hashlib.md5(refresh_claims['jti'].encode()).digest().hex()
	refresh_expiry = datetime.utcfromtimestamp(refresh_claims['exp'])

	async with db_connection.transaction():
		await db_connection.execute(remove_refresh, found_refresh['id'])
		await db_connection.execute(insert_refresh, login, refresh_hash,
			refresh_expiry, access_claims['jti'])

	access_token = pavao.http.generateToken(access_claims)
	refresh_token = pavao.http.generateToken(refresh_claims)

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

