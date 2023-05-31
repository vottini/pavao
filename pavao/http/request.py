
import urllib

from ..exception import PavaoException
class RequestException(PavaoException):
	pass

_set_cookie = "set-cookie"
_utf8_decode = lambda content : content.decode('utf-8')
_enlist_value = lambda value : value if isinstance(value, list) else [value]

class Request:
	class Address:
		def __init__(self, ip, port):
			self.ip = ip
			self.port = port

		def __str__(self): return f"{self.ip}:{self.port}"

	def __init__(self, scope):
		self.method = scope['method']
		self.path = scope['path']
		self.destination = Request.Address(*scope['server'])
		self.source = Request.Address(*scope['client'])

		self.headers = dict()
		for header_name, header_value in scope['headers']:

			try:
				decoded_name = _utf8_decode(header_name)
				decoded_value = _utf8_decode(header_value)

				# 'set-cookie' has its own semantics
				# https://www.rfc-editor.org/rfc/rfc7230#section-3.2.2

				if decoded_name != _set_cookie:
					value_tokens = [ token.strip() for token in decoded_value.split(',') ]

					decoded_value = (value_tokens[0]
						if len(value_tokens) == 1
						else value_tokens)

				if not decoded_name in self.headers:
					self.headers[decoded_name] = decoded_value
					continue

				value = self.headers[decoded_name]
				existing_value = _enlist_value(value)
				decoded_value = _enlist_value(decoded_value)
				self.headers[decoded_name] = existing_value + decoded_value

			except (UnicodeError, UnicodeDecodeError) as e:
				msg = f'Error decoding headers: "{e}"'
				raise RequestException(msg)

		self.params = dict()
		query_string = scope['query_string']

		if len(query_string) > 0:

			try:
				saned_qs = query_string.decode().replace('+',' ')
				unquoted_params = urllib.parse.unquote(saned_qs, errors='strict')
				params_pairs = unquoted_params.split("&")

				for pair in params_pairs:
					param_tokens = pair.split('=', 1)
					param_value = param_tokens[1] if len(param_tokens) > 1 else True
					self.params[param_tokens[0]] = param_value

			except (UnicodeError, UnicodeDecodeError) as e:
				msg = f"Error decoding params: '{e}'"
				raise RequestException(msg)

	def __str__(self): # pragma: no cover
		return f"""
			method = {self.method}
			path = {self.path}
			source = {self.source}
			destination = {self.destination}
			headers = {self.headers}
			params = {self.params}
		"""

#-------------------------------------------------------------------------------

__all__ = [
	"RequestException",
	"Request"
]

