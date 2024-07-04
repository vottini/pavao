
import re
import urllib

from ..exception import PavaoException
class RequestException(PavaoException):
	pass

_cookie = "cookie"
_set_cookie = "set-cookie"
_cookie_pattern = re.compile(r"([^=]+)=(\S*)")
_quality_matcher = re.compile(r'^q=(1|0.[0-9]{1,3})$')
_any_language = '*'

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
		self.cookies = dict()

		for header_name, header_value in scope['headers']:

			try:
				decoded_name = _utf8_decode(header_name)
				decoded_value = _utf8_decode(header_value)

				if decoded_name == _cookie:
					cookie_pairs = decoded_value.split(';')
					cookie_pairs = [ cookie_pair.strip() for cookie_pair in cookie_pairs ]

					for cookie_pair in cookie_pairs:
						found_values = _cookie_pattern.search(cookie_pair)
						if found_values is None:
							continue

						try:
							name, value = found_values.groups()
							self.cookies[name] = value

						except Exception:
							continue

					continue

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

	# see more on
	# https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Accept-Language
	# https://developer.mozilla.org/en-US/docs/Glossary/Quality_values

	def parse_locale_priority(self):

		"""
			returns a list of accepted localizations for this request, in order
			of priority. if no localization was specified or no priority exists,
			an empty list is returned
		"""

		accepted_languages = self.headers.get('accept-language')
		if accepted_languages is None:
			return list()

		if isinstance(accepted_languages, str):
			parts = accepted_languages.split(';', maxsplit=1)
			languageId = parts[0].strip().replace('-','_')

			return (languageId
				if languageId != _any_language
				else list())

		parsed_localization = list()
		for localization_priority in accepted_languages:
			parts = localization_priority.split(';', maxsplit=1)
			languageId = parts[0].strip().replace('-','_')
			if _any_language == languageId:
				continue

			quality = 1.0
			if len(parts) > 1:
				quality_part = parts[1]
				found = _quality_matcher.match(quality_part)

				if None != found:
					quality_str = found.group(1)
					quality = float(quality_str)

			parsed_localization.append((languageId, quality))

		return [ locale[0]
			for locale in sorted(
				parsed_localization,
				key=lambda x : x[1],
				reverse=True)
		]

#-------------------------------------------------------------------------------

__all__ = [
	"RequestException",
	"Request"
]

