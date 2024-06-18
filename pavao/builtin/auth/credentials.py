
import asyncio
import secrets
from datetime import timedelta

_token_schema = {
	"issuer": str,
	"validity": {
		"access_minutes": 10,
		"refresh_minutes": 360
	}
}

token_settings = None
async def setup(settings):
	global token_settings

	token_settings = settings.get_setting(
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

__all__ = [
	"setup",
	"access_validity",
	"refresh_validity",
	"create_claims"
]

