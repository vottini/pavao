
import secrets
import json
import base64
import hashlib
import hmac

from datetime import datetime
from datetime import timedelta
from datetime import timezone

from pavao import Logger

class SecretKey:
	def __init__(self):
		self.ident = secrets.token_urlsafe(5)
		self.key = secrets.token_bytes(32)
		self.exp = None

_current = SecretKey()
_past_keys = dict()

#-------------------------------------------------------------------------------

def refresh_secret_key(previous_validity=None):

	"""
		Replaces the current secret key used to sign internal jwt tokens.
		If previous_validity contains an int (number of days) or a
		datetime.timedelta instance, this value will serve as the interval
		while the previous secret key will remain valid. More than one previous
		secret key may remain valid at the same time.
	"""

	global _current, _past_keys

	if previous_validity is not None:
		if isinstance(previous_validity, int) and previous_validity > 0:
			previous_validity = timedelta(days=previous_validity)

		if not isinstance(previous_validity, timedelta):
			Logger.error(f"Bad argument to refresh_secret_key [{previous_validity}]")
			Logger.error(f"Secret key refresh aborted")
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

	if previous_validity is not None:
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

def calc_current_signature(content):
	global _current

	signature = hmac.digest(
		_current.key,
		content.encode(),
		hashlib.sha256)

	return base64url(signature)


def generate_token(claims):
	global _current

	header = {
		"alg": "HS256",
		"typ": "JWT",
		"kid": _current.ident
	}

	header_base64 = _serializedToBase64(header)
	payload_base64 = _serializedToBase64(claims)
	contents = header_base64 + "." + payload_base64
	signature = calc_current_signature(contents)
	return contents + "." + signature


def validate_token(token):
	global _current, _past_keys
	previous_keys = _past_keys
	current_key = _current

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
	if generator_ident is None:
		return None

	generator = (current_key
		if current_key.ident == generator_ident
		else previous_keys.get(generator_ident))

	if generator is None:
		return None

	if generator.exp is not None:
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
	'refresh_secret_key',
	'calc_current_signature',
	'generate_token',
	'validate_token'
]

