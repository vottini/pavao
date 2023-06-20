
import secrets
from datetime import datetime, timedelta, timezone
import json
import base64
import hashlib
import hmac

class SecretKey:
	def __init__(self):
		self.ident = secrets.token_urlsafe(5)
		self.key = secrets.token_bytes(32)
		self.exp = None

_current = SecretKey()
_past_keys = dict()

#-------------------------------------------------------------------------------

def refresh_secretKey(previous_validity=None):
	global _current, _past_keys

	if None != previous_validity:
		if isinstance(previous_validity, int) and previous_validity > 0:
			previous_validity = timedelta(days=previous_validity)

		if not isinstance(previous_validity, timedelta):
			print("Bad argument passed to refresh_secretKey(), aborting refresh")
			return False

	current_time = datetime.now(tz=timezone.utc)
	previous = _current

	candidate = SecretKey()
	while candidate.ident in _past_keys:
		candidate = SecretKey() # pragma: no cover

	filtered = dict()
	for secret_key in _past_keys.values():
		if secret_key.exp > current_time:
			filtered[secret_key.ident] = secret_key

	if None != previous_validity:
		previous.exp = current_time + previous_validity
		filtered[previous.ident] = previous

	_past_keys = filtered
	_current = candidate
	return True

#-------------------------------------------------------------------------------

def base64url(contents):
	base64_encoded = base64.urlsafe_b64encode(contents)
	base64_decoded = base64_encoded.decode()
	return base64_decoded.strip('=')


_compact_separators = (',', ':')
def _serializedToBase64(contents):
	serialized = json.dumps(contents, separators=_compact_separators)
	return base64url(serialized.encode())

#-------------------------------------------------------------------------------

def calcCurrentSignature(content):
	global _current

	signature = hmac.digest(
		_current.key,
		content.encode(),
		hashlib.sha256)

	return base64url(signature)


def generateToken(claims):
	global _current

	header = {
		"alg": "HS256",
		"typ": "JWT",
		"kid": _current.ident
	}

	header_base64 = _serializedToBase64(header)
	payload_base64 = _serializedToBase64(claims)
	contents = header_base64 + "." + payload_base64
	signature = calcCurrentSignature(contents)
	return contents + "." + signature


def validateToken(token):
	global _current, _past_keys
	components = token.split('.')
	if len(components) != 3:
		return None

	header_str, claims_str, token_signature = components

	try:
		header_base64 = header_str + "==="
		header_json = base64.urlsafe_b64decode(header_base64)
		header = json.loads(header_json.decode())

	except Exception as e:
		return None

	generator_ident = header.get('kid')
	if None == generator_ident:
		return None

	generator = (_current
		if _current.ident == generator_ident
		else _past_keys.get(generator_ident))

	if None == generator:
		return None

	if None != generator.exp:
		if generator.exp < datetime.now(tz=timezone.utc):
			return None

	contents = header_str + "." + claims_str
	calced_signature = hmac.digest(
		generator.key,
		contents.encode(),
		hashlib.sha256)

	if base64url(calced_signature) != token_signature:
		return None

	try:
		claims_base64 = claims_str + "==="
		claims_json = base64.urlsafe_b64decode(claims_base64)
		return json.loads(claims_json.decode())

	except Exception as e:
		return None

#-------------------------------------------------------------------------------

__all__ = [
	'refresh_secretKey',
	'calcCurrentSignature',
	'generateToken',
	'validateToken'
]

