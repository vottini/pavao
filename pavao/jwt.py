
import secrets
import json
import base64
import hashlib
import hmac

from datetime import datetime
from datetime import timedelta
from datetime import timezone

from .logger import Logger

class SecretKey:
	def __init__(self):
		self.ident = secrets.token_urlsafe(5)
		self.key = secrets.token_bytes(32)
		self.exp = None

	
def base64url(contents):
	base64_encoded = base64.urlsafe_b64encode(contents)
	base64_decoded = base64_encoded.decode()
	return base64_decoded.strip('=')


_compact_separators = (',', ':')
def _serializedToBase64(contents):
	serialized = json.dumps(contents, separators=_compact_separators)
	return base64url(serialized.encode())

#-------------------------------------------------------------------------------

class JwtSupplier:
	def __init__(self):
		self.current_key = SecretKey()
		self.past_keys = dict()

	def refresh_secret_key(self, previous_validity=None):
	
		"""
			Replaces the current secret key used to sign jwt tokens.
			If previous_validity contains an int (number of days) or a
			datetime.timedelta instance, this value will serve as the
			valid interval for the previous secret key. More than one previous
			secret key may remain valid at the same time.
		"""
	
		if previous_validity is not None:
			if isinstance(previous_validity, int) and previous_validity > 0:
				previous_validity = timedelta(days=previous_validity)
	
			if not isinstance(previous_validity, timedelta):
				Logger.error(f"Bad argument to refresh_secret_key [{previous_validity}]")
				Logger.error(f"Secret key refresh aborted")
				return False
	
		current_time = datetime.now(tz=timezone.utc)
		previous = self.current_key
	
		candidate = SecretKey()
		while candidate.ident in self.past_keys:
			candidate = SecretKey() # pragma: no cover
	
		filtered = dict()
		for secret_key in self.past_keys.values():
			if secret_key.exp > current_time:
				filtered[secret_key.ident] = secret_key
	
		if previous_validity is not None:
			previous.exp = current_time + previous_validity
			filtered[previous.ident] = previous
	
		self.past_keys = filtered
		self.current_key = candidate
		return True
	
	#-------------------------------------------------------------------------------
	
	def calc_current_signature(self, content):

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
	
		header_base64 = _serializedToBase64(header)
		payload_base64 = _serializedToBase64(claims)
		contents = header_base64 + "." + payload_base64
		signature = self.calc_current_signature(contents)
		return contents + "." + signature
	
	
	def validate_token(self, token):
		previous_keys = self.past_keys
		current = self.current_key
	
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
	
		generator = (current
			if current.ident == generator_ident
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

