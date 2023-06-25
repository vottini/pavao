
from ..exception import PavaoException

class SameSite:
	STRICT = 0
	LAX = 1
	NONE = 2

_same_site_options = {
	SameSite.STRICT: "Strict",
	SameSite.LAX: "Lax",
	SameSite.NONE: "None"
}


# https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Set-Cookie
# https://stackoverflow.com/questions/1969232/what-are-allowed-characters-in-cookies
# https://www.ietf.org/rfc/rfc6265.txt

class Cookie:
	def __init__(self, name, value):
		self.name = name
		self.value = str(value)
		self.domain = None
		self.path = None

		self.httpOnly = False
		self.expires = None
		self.maxAge = None
		self.secure = False
		self.sameSite = "Lax"

	#---------------------------------------------------------------------------

	def set_domain(self, domain):
		self.domain = domain
		return self

	def set_path(self, path):
		self.path = path
		return self

	def set_httpOnly(self, value=True):
		self.httpOnly = value
		return self

	def set_expires(self, date):
		self.expires = date.strftime('%a, %d %b %Y %H:%M:%S GMT')
		return self

	def set_maxAge(self, seconds):
		self.maxAge = seconds
		return self

	def set_secure(self, value=True):
		self.secure = value
		return self

	def set_sameSite(self, value):
		if not value in _same_site_options:
			raise PavaoException("Not a valid SameSite value")

		value = _same_site_options[value]
		self.sameSite = value
		return self

	#---------------------------------------------------------------------------

	def get_identifier(self):
		return (
			self.name,
			self.domain,
			self.path
		)

	#---------------------------------------------------------------------------

	def append_domain(self, result):
		return (result + '; Domain=' + self.domain
			if self.domain is not None
			else result)

	def append_path(self, result):
		return (result + '; Path=' + self.path
			if self.path is not None
			else result)

	def append_maxAge(self, result):
		return (result + '; Max-Age=' + self.maxAge
			if self.maxAge is not None
			else result)

	def append_expires(self, result):
		return (result + '; Expires=' + self.expires
			if self.expires is not None
			else result)

	def append_sameSite(self, result):
		return (result + '; SameSite=' + self.sameSite
			if self.sameSite != "Lax"
			else result)

	def append_secure(self, result):
		return (result + '; Secure'
			if self.secure
			else result)

	def append_httpOnly(self, result):
		return (result + '; HttpOnly'
			if self.httpOnly
			else result)

	#---------------------------------------------------------------------------

	def __str__(self):
		result = f"{self.name}={self.value}"
		result = self.append_domain(result)
		result = self.append_path(result)
		result = self.append_maxAge(result)
		result = self.append_expires(result)
		result = self.append_sameSite(result)
		result = self.append_secure(result)
		result = self.append_httpOnly(result)
		return result

