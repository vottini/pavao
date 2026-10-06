
import sys
sys.path.append('..')

import pytest
import pavao
from datetime import datetime, timezone

#-------------------------------------------------------------------------------

def testValidCookie():
	cookie = pavao.http.Cookie('session', 'abc123')
	assert cookie.name == 'session'
	assert cookie.value == 'abc123'

def testInvalidName():
	for char in ' \t\n(),/:;<=>?@{}\\\"':
		with pytest.raises(pavao.http.CookieException):
			pavao.http.Cookie(char + 'name', 'value')

def testInvalidValue():
	for char in ' \t\n,;\\\"':
		with pytest.raises(pavao.http.CookieException):
			pavao.http.Cookie('name', char + 'value')

def testIntValueIsStringified():
	cookie = pavao.http.Cookie('count', 42)
	assert cookie.value == '42'

def testSetCookieHeader():
	result = str(pavao.http.Cookie('a', 'b'))
	assert result == 'a=b'

def testDomain():
	result = str(pavao.http.Cookie('a', 'b').set_domain('example.com'))
	assert 'Domain=example.com' in result

def testPath():
	result = str(pavao.http.Cookie('a', 'b').set_path('/api'))
	assert 'Path=/api' in result

def testHttpOnly():
	result = str(pavao.http.Cookie('a', 'b').set_httpOnly())
	assert 'HttpOnly' in result

	result = str(pavao.http.Cookie('a', 'b').set_httpOnly(False))
	assert 'HttpOnly' not in result

def testSecure():
	result = str(pavao.http.Cookie('a', 'b').set_secure())
	assert 'Secure' in result

	result = str(pavao.http.Cookie('a', 'b').set_secure(False))
	assert 'Secure' not in result

def testExpires():
	dt = datetime(2099, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
	result = str(pavao.http.Cookie('a', 'b').set_expires(dt))
	assert 'Expires=Thu, 01 Jan 2099 00:00:00 GMT' in result

def testExpiresRejectsNaiveDatetime():
	with pytest.raises(pavao.http.CookieException):
		pavao.http.Cookie('a', 'b').set_expires(datetime(2099, 1, 1))

def testMaxAge():
	result = str(pavao.http.Cookie('a', 'b').set_maxAge(3600))
	assert 'Max-Age=3600' in result

def testMaxAgeRejectsNegative():
	with pytest.raises(pavao.http.CookieException):
		pavao.http.Cookie('a', 'b').set_maxAge(-1)

def testMaxAgeRejectsFloat():
	with pytest.raises(pavao.http.CookieException):
		pavao.http.Cookie('a', 'b').set_maxAge(1.5)

def testSameSiteStrict():
	result = str(pavao.http.Cookie('a', 'b').set_sameSite(pavao.http.SameSite.STRICT))
	assert 'SameSite=Strict' in result

def testSameSiteLaxIsDefault():
	# Lax is the default and is omitted from the header (browser default)
	result = str(pavao.http.Cookie('a', 'b'))
	assert 'SameSite' not in result

def testSameSiteNone():
	result = str(pavao.http.Cookie('a', 'b').set_sameSite(pavao.http.SameSite.NONE))
	assert 'SameSite=None' in result
	assert 'Secure' in result  # SameSite=None must imply Secure

def testSameSiteInvalid():
	with pytest.raises(pavao.http.CookieException):
		pavao.http.Cookie('a', 'b').set_sameSite(99)

def testSetToBeRemoved():
	result = str(pavao.http.Cookie('a', 'b').set_to_be_removed())
	assert 'Expires=Thu, 01 Jan 1970 00:00:00 GMT' in result

def testGetIdentifier():
	cookie = pavao.http.Cookie('a', 'b').set_domain('x.com').set_path('/p')
	assert cookie.get_identifier() == ('a', 'x.com', '/p')

def testMethodChaining():
	cookie = (pavao.http.Cookie('a', 'b')
		.set_domain('x.com')
		.set_path('/')
		.set_httpOnly()
		.set_secure()
		.set_maxAge(60)
		.set_sameSite(pavao.http.SameSite.STRICT)
	)
	assert isinstance(cookie, pavao.http.Cookie)

#-------------------------------------------------------------------------------

if __name__ == "__main__":
	testValidCookie()
	testInvalidName()
	testInvalidValue()
	testIntValueIsStringified()
	testSetCookieHeader()
	testDomain()
	testPath()
	testHttpOnly()
	testSecure()
	testExpires()
	testMaxAge()
	testSameSiteStrict()
	testSameSiteLaxIsDefault()
	testSameSiteNone()
	testSameSiteInvalid()
	testSetToBeRemoved()
	testGetIdentifier()
	testMethodChaining()
