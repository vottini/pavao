
import asyncio
import argon2
from datetime import datetime, timezone
import hashlib

import pavao
import auth.credentials as credentials

retrieve_password_hash = pavao.include('queries/retrieve_password_hash.sql')
update_password_hash = pavao.include('queries/update_password_hash.sql')

blueprints = pavao.pathTo('blueprints.jbp')
localized_messages = pavao.include('messages.ini')
localization = pavao.Localization(localized_messages)

#-------------------------------------------------------------------------------

@pavao.acceptsJson(fileBlueprint=blueprints, withRoot="passwordUpdate")
async def process(request, response, db_connection, auth_data, parsed_json):
	localizer = localization.create_localizer(request)
	hasher = argon2.PasswordHasher()

	try:
		storedPassword = await db_connection.fetchval(
			retrieve_password_hash,
			auth_data.account_id)

		hasher.verify(
			storedPassword,
			parsed_json.oldPassword)

		newHashedPassword = hasher.hash(parsed_json.newPassword)
		await db_connection.execute(update_password_hash, newHashedPassword,
			auth_data.account_id)

	except argon2.exceptions.VerifyMismatchError:
		await asyncio.sleep(3)

		response.set_status(400)
		return localizer.create_error(
			"INVALID_CREDENTIALS"
		)

	except Exception as e:
		msg = f"Error updating password: {e}"
		pavao.Logger.error(msg)

		response.set_status(500)
		return localizer.create_error(
			"INTERNAL_ERROR"
		)

#-------------------------------------------------------------------------------

def pavao_endpoint():

	return {
		'method': 'POST',
		'path': '/change-password',
		'processor': process
	}

