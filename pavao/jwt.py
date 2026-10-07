
import secrets
import json
import base64
import hashlib
import hmac

from datetime import datetime, timedelta, timezone

from .logger import Logger


class SecretKey:
	def __init__(self):
		self.ident = secrets.token_urlsafe(5)
		self.key   = secrets.token_bytes(32)
		self.exp   = None  # set only when placed in past_keys


def base64url(contents):
	return base64.urlsafe_b64encode(contents).decode().strip('=')


_compact_separators = (',', ':')

def _serialize_to_base64(contents):
	serialized = json.dumps(contents, separators=_compact_separators)
	return base64url(serialized.encode())

#-------------------------------------------------------------------------------

class JwtSupplier:
	def __init__(self):
		self.current_key = SecretKey()
		self.past_keys   = dict()


	def refresh_secret_key(self, previous_validity=None):
		if previous_validity is not None:
			if isinstance(previous_validity, int) and previous_validity > 0:
				previous_validity = timedelta(days=previous_validity)

			if not isinstance(previous_validity, timedelta):
				Logger.error(f"Bad argument to refresh_secret_key [{previous_validity}]")
				Logger.error(f"Secret key refresh aborted")
				return False

			if previous_validity.total_seconds() <= 0:
				Logger.error(f"previous_validity must be positive, got {previous_validity}")
				Logger.error(f"Secret key refresh aborted")
				return False

		current_time = datetime.now(tz=timezone.utc)
		previous = self.current_key

		candidate = SecretKey()
		while candidate.ident in self.past_keys:
			candidate = SecretKey()  # pragma: no cover

		filtered = {
			sk.ident: sk
			for sk in self.past_keys.values()
			if sk.exp > current_time
		}

		if previous_validity is not None:
			previous.exp = current_time + previous_validity
			filtered[previous.ident] = previous

		self.past_keys   = filtered
		self.current_key = candidate
		return True


	def _calc_signature(self, content):
		signature = hmac.digest(
			self.current_key.key,
			content.encode(),
			hashlib.sha256)
		return base64url(signature)


	def generate_token(self, claims):
		header = {
			"alg": "HS256",
			"typ": "JWT",
			"kid": self.current_key.ident
		}

		header_b64  = _serialize_to_base64(header)
		payload_b64 = _serialize_to_base64(claims)
		contents    = header_b64 + "." + payload_b64
		signature   = self._calc_signature(contents)
		return contents + "." + signature


	def validate_token(self, token):
		components = token.split('.')
		if len(components) != 3:
			return None

		header_str, claims_str, token_signature = components

		try:
			header = json.loads(
				base64.urlsafe_b64decode(header_str + "===").decode())
		except Exception:
			return None

		if header.get('alg') != 'HS256':
			return None

		generator_ident = header.get('kid')
		if generator_ident is None:
			return None

		current = self.current_key
		generator = (current
			if current.ident == generator_ident
			else self.past_keys.get(generator_ident))

		if generator is None:
			return None

		if generator.exp is not None:
			if generator.exp < datetime.now(tz=timezone.utc):
				return None

		contents = header_str + "." + claims_str
		expected_signature = base64url(hmac.digest(
			generator.key,
			contents.encode(),
			hashlib.sha256))

		if expected_signature != token_signature:
			return None

		try:
			return json.loads(
				base64.urlsafe_b64decode(claims_str + "===").decode())
		except Exception:
			return None
