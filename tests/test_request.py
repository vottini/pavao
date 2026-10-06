
import sys
sys.path.append('..')

import pytest
import pavao

def testBadUtf8():

	# https://stackoverflow.com/a/3886015
	# https://www.php.net/manual/en/reference.pcre.pattern.modifiers.php#54805

	invalid_sequences = (
		b'\xfc',             # Invalid Start Byte
		b'\xc3\x28',         # Invalid 2 Octet Sequence
		b'\xa0\xa1',         # Invalid Sequence Identifier'
		b'\xe2\x28\xa1',     # Invalid 3 Octet Sequence (in 2nd Octet)
		b'\xe2\x82\x28',     # Invalid 3 Octet Sequence (in 3rd Octet)
		b'\xf0\x28\x8c\xbc', # Invalid 4 Octet Sequence (in 2nd Octet)
		b'\xf0\x90\x28\xbc', # Invalid 4 Octet Sequence (in 3rd Octet)
		b'\xf0\x28\x8c\x28', # Invalid 4 Octet Sequence (in 4th Octet)
	)

	base_scope = {
		'server': ('127.0.0.1', 8000),
		'client': ('127.0.0.1', 46648),
		'method': 'GET',
		'path': '/invalid/strings',
		'query_string': b'',
	}

	for sequence in invalid_sequences:
		with pytest.raises(pavao.http.RequestException):
			full_scope = { **base_scope, 'headers': [(b'invalid-header', sequence)] }
			pavao.http.Request(full_scope)

#-------------------------------------------------------------------------------

def testMultipleHeaders():

	base_scope = {
		'server': ('127.0.0.1', 8000),
		'client': ('127.0.0.1', 46648),
		'method': 'GET',
		'path': '/multiple/headers',
		'query_string': b'',
	}

	header_name = 'test-header'
	comma_separated = ((header_name.encode(), b'foo, bar'),)

	multiple_times = (
		(header_name.encode(), b'foo'),
		(header_name.encode(), b'bar')
	)

	result_expected = ['foo', 'bar']
	for method in [comma_separated, multiple_times]:
		request = pavao.http.Request({**base_scope, 'headers': method})
		parsed_header = request.headers[header_name]

		num_obtained = len(parsed_header)
		assert num_obtained == len(result_expected)
		for i in range(num_obtained):
			assert parsed_header[i] == result_expected[i]

#-------------------------------------------------------------------------------

def testInternationalHeaders():
	international_headers = {
		'chinese-header': '测试标头解析',
		'thai-header': 'การทดสอบการแยกวิเคราะห์ส่วนหัว',
		'hebrew-header': 'בדיקת ניתוח כותרות',
		'japanese-header': 'ヘッダー解析のテスト'
	}
	
	scope = {
		'server': ('127.0.0.1', 8000),
		'client': ('127.0.0.1', 46648),
		'method': 'GET',
		'path': '/unicode/headers',
		'query_string': b'',
		'headers': tuple(
			map(lambda key : (
				key.encode(),
				international_headers[key].encode()
			), international_headers.keys())
		)
	}

	request = pavao.http.Request(scope)
	for header_name, header_value in request.headers.items():
		assert international_headers[header_name] == header_value

#-------------------------------------------------------------------------------

def testParseParams():

	params_list = (
		(b'', {}),
		(b'a=1000', {'a': "1000"}),
		(b'a=1000&b=2000', {'a': "1000", 'b': "2000"}),
		(b'c=1e3%3D1000', {'c': "1e3=1000"}),
		(b'd=%2Fpath%2Fto%2Fgo', {'d': r"/path/to/go"}),
		(b'e=text+containing+++whitespace&f', {'e': "text containing   whitespace", 'f': True}),
		(b'g=%7B%C3%A1+%C3%A9+isso+ai%21%7D', {'g': "{á é isso ai!}"}),
		(b'h=v%C3%A1rios+++%25++%2B%2B++sinais+%24+e+%3D+um+kanji+%E6%9E%97+cara+de+mal+%3A%3C', {'h': "vários   %  ++  sinais $ e = um kanji 林 cara de mal :<"})
	)

	base_scope = {
		'server': ('127.0.0.1', 8000),
		'client': ('127.0.0.1', 46648),
		'method': 'GET',
		'path': '/parse/params',
		'headers': [],
	}

	for raw_params, expected in params_list:
		full_scope = { **base_scope, 'query_string': raw_params }
		request = pavao.http.Request(full_scope)
		parsed_params = request.params

		for key, value in expected.items():
			assert key in parsed_params
			assert value == parsed_params[key]

	invalid_sequences = (
		b'a=\xfc',             # Invalid Start Byte
		b'\xc3\x28=bad',       # Invalid 2 Octet Sequence
		b'c=good&d=\xa0\xa1',  # Invalid Sequence Identifier'
		b'd=\xe2\x28\xa1',     # Invalid 3 Octet Sequence (in 2nd Octet)
		b'e=\xe2\x82\x28',     # Invalid 3 Octet Sequence (in 3rd Octet)
		b'f=\xf0\x28\x8c\xbc', # Invalid 4 Octet Sequence (in 2nd Octet)
		b'g=\xf0\x90\x28\xbc', # Invalid 4 Octet Sequence (in 3rd Octet)
		b'h=\xf0\x28\x8c\x28', # Invalid 4 Octet Sequence (in 4th Octet)
	)

	for sequence in invalid_sequences:
		with pytest.raises(pavao.http.RequestException):
			full_scope = { **base_scope, 'query_string': sequence }
			pavao.http.Request(full_scope)

#-------------------------------------------------------------------------------

def testCookieParsing():

	base_scope = {
		'server': ('127.0.0.1', 8000),
		'client': ('127.0.0.1', 46648),
		'method': 'GET',
		'path': '/cookies',
		'query_string': b'',
	}

	# single cookie
	scope = {**base_scope, 'headers': [(b'cookie', b'session=abc123')]}
	request = pavao.http.Request(scope)
	assert request.cookies['session'] == 'abc123'

	# multiple cookies separated by semicolons
	scope = {**base_scope, 'headers': [(b'cookie', b'a=1; b=2; c=3')]}
	request = pavao.http.Request(scope)
	assert request.cookies['a'] == '1'
	assert request.cookies['b'] == '2'
	assert request.cookies['c'] == '3'

	# cookie with no value (valueless cookie)
	scope = {**base_scope, 'headers': [(b'cookie', b'flag=')]}
	request = pavao.http.Request(scope)
	assert 'flag' in request.cookies

	# malformed cookie pair (no '=') is silently skipped, valid ones still parsed
	scope = {**base_scope, 'headers': [(b'cookie', b'malformed; good=yes')]}
	request = pavao.http.Request(scope)
	assert 'good' in request.cookies
	assert 'malformed' not in request.cookies

	# set-cookie must NOT be split on comma (RFC 7230 exception)
	set_cookie_value = 'id=abc; Path=/; Expires=Thu, 01 Jan 2099 00:00:00 GMT'
	scope = {**base_scope, 'headers': [(b'set-cookie', set_cookie_value.encode())]}
	request = pavao.http.Request(scope)
	assert request.headers['set-cookie'] == set_cookie_value

#-------------------------------------------------------------------------------

def testLocalePriority():

	base_scope = {
		'server': ('127.0.0.1', 8000),
		'client': ('127.0.0.1', 46648),
		'method': 'GET',
		'path': '/locale',
		'query_string': b'',
	}

	def make_request(accept_language):
		headers = [(b'accept-language', accept_language.encode())] if accept_language else []
		return pavao.http.Request({**base_scope, 'headers': headers})

	# no header → empty list
	request = pavao.http.Request({**base_scope, 'headers': []})
	assert request.parse_locale_priority() == []

	# wildcard only → empty list
	assert make_request('*').parse_locale_priority() == []

	# single value → list with one entry (not a bare string)
	result = make_request('pt_BR').parse_locale_priority()
	assert isinstance(result, list)
	assert result == ['pt_BR']

	# dash normalised to underscore
	result = make_request('zh-CN').parse_locale_priority()
	assert result == ['zh_CN']

	# multiple values sorted by quality
	result = make_request('en-US,zh-CN;q=0.9,ja;q=0.8').parse_locale_priority()
	assert result == ['en_US', 'zh_CN', 'ja']

	# explicit lower quality comes last
	result = make_request('fr;q=0.5,de;q=0.9').parse_locale_priority()
	assert result == ['de', 'fr']

	# wildcard mixed in is ignored, rest is preserved
	result = make_request('en-GB,*;q=0.5').parse_locale_priority()
	assert 'en_GB' in result
	assert '*' not in result

	# space after semicolon is legal (RFC 7231) and must be parsed correctly
	result = make_request('en-US, zh-CN; q=0.9').parse_locale_priority()
	assert result == ['en_US', 'zh_CN']

	# q=1.0 and q=1.000 are valid per RFC 7231
	result = make_request('en;q=1.0,fr;q=0.5').parse_locale_priority()
	assert result == ['en', 'fr']

#-------------------------------------------------------------------------------

def testSecurityQueryParams():

	base_scope = {
		'server': ('127.0.0.1', 8000),
		'client': ('127.0.0.1', 46648),
		'method': 'GET',
		'path': '/security',
		'headers': [],
	}

	# null byte injection via percent-encoding must be rejected
	null_byte_payloads = (
		b'file=%00etc%2Fpasswd',    # null byte in value
		b'%00key=value',            # null byte in key
		b'a=1&b=%00',              # null byte in second param
		b'x=normal%00injected',    # null byte mid-value
	)

	for payload in null_byte_payloads:
		with pytest.raises(pavao.http.RequestException):
			pavao.http.Request({**base_scope, 'query_string': payload})

	# parameter pollution must be rejected
	duplicate_payloads = (
		b'role=user&role=admin',
		b'a=1&b=2&a=3',
		b'x=first&x=second',
	)

	for payload in duplicate_payloads:
		with pytest.raises(pavao.http.RequestException):
			pavao.http.Request({**base_scope, 'query_string': payload})

	# empty key must be rejected
	with pytest.raises(pavao.http.RequestException):
		pavao.http.Request({**base_scope, 'query_string': b'=value'})

	# legitimate requests must still pass
	pavao.http.Request({**base_scope, 'query_string': b'a=1&b=2&c=3'})

#-------------------------------------------------------------------------------

if __name__ == "__main__":
	testBadUtf8()
	testMultipleHeaders()
	testInternationalHeaders()
	testParseParams()
	testCookieParsing()
	testLocalePriority()

