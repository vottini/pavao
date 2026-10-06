
import sys
sys.path.append('..')

import pytest
import pavao
from pavao.http.response import emit, emit_headers, emit_body

#-------------------------------------------------------------------------------

class Collector:
	def __init__(self):
		self.messages = []

	async def __call__(self, message):
		self.messages.append(message)

def make_response():
	return pavao.http.Response(Collector())

#-------------------------------------------------------------------------------

def testDefaults():
	response = make_response()
	assert response.status == 200
	assert response.complete == False
	assert response.headers_sent == False
	assert response.body_sent == False
	assert response.content == b""
	assert response.headers == {}
	assert response.cookies == {}

def testSetStatus():
	response = make_response()
	response.set_status(404)
	assert response.status == 404
	assert response.complete == True

def testSetStatusWithoutComplete():
	response = make_response()
	response.set_status(404, set_complete=False)
	assert response.status == 404
	assert response.complete == False

def testAddHeader():
	response = make_response()
	response.add_header('x-custom', 'value')
	assert response.headers['x-custom'] == 'value'

def testSetContent():
	response = make_response()
	response.set_content('application/json', b'{"ok":true}')
	assert response.headers['content-type'] == 'application/json'
	assert response.headers['content-length'] == '11'
	assert response.content == b'{"ok":true}'

def testSetContentWithoutBody():
	response = make_response()
	response.set_content('application/octet-stream')
	assert response.headers['content-type'] == 'application/octet-stream'
	assert 'content-length' not in response.headers
	assert response.content == b""

def testSetPlainText():
	response = make_response()
	ret = response.set_plain_text('Olá, 世界')
	assert ret is response  # must return self for chaining
	assert response.headers['content-type'] == 'text/plain; charset=utf-8'
	assert response.content == 'Olá, 世界'.encode('utf-8')
	assert response.headers['content-length'] == str(len(response.content))

def testContentLengthIsByteCount():
	# content-length must be byte count, not char count (matters for multibyte)
	text = '林'  # 3 bytes in UTF-8, 1 char
	response = make_response()
	response.set_plain_text(text)
	assert response.headers['content-length'] == '3'

def testAddCookie():
	response = make_response()
	cookie = pavao.http.Cookie('session', 'abc')
	response.add_cookie(cookie)
	assert cookie.get_identifier() in response.cookies

def testMethodChaining():
	response = make_response()
	ret = (response
		.set_status(201, set_complete=False)
		.add_header('x-foo', 'bar')
		.set_content('text/plain; charset=utf-8', b'ok')
	)
	assert ret is response

#-------------------------------------------------------------------------------

@pytest.mark.asyncio
async def testEmitHeaders():
	response = make_response()
	response.add_header('content-type', 'text/plain; charset=utf-8')
	response.set_status(201)

	await emit_headers(response)

	assert response.headers_sent == True
	assert len(response.send_fnc.messages) == 1
	msg = response.send_fnc.messages[0]
	assert msg['type'] == 'http.response.start'
	assert msg['status'] == 201
	assert (b'content-type', b'text/plain; charset=utf-8') in msg['headers']

@pytest.mark.asyncio
async def testEmitHeadersIsIdempotent():
	response = make_response()
	await emit_headers(response)
	await emit_headers(response)
	assert len(response.send_fnc.messages) == 1

@pytest.mark.asyncio
async def testEmitHeadersIncludesCookies():
	response = make_response()
	response.add_cookie(pavao.http.Cookie('token', 'xyz'))

	await emit_headers(response)

	headers = response.send_fnc.messages[0]['headers']
	cookie_headers = [v for k, v in headers if k == b'set-cookie']
	assert len(cookie_headers) == 1
	assert b'token=xyz' in cookie_headers[0]

@pytest.mark.asyncio
async def testEmitBody():
	response = make_response()
	await emit_headers(response)
	await emit_body(response, b'hello')

	assert response.body_sent == True
	msg = response.send_fnc.messages[1]
	assert msg['type'] == 'http.response.body'
	assert msg['body'] == b'hello'
	assert msg['more_body'] == False

@pytest.mark.asyncio
async def testEmitBodyIsIdempotent():
	response = make_response()
	await emit_headers(response)
	await emit_body(response, b'first')
	await emit_body(response, b'second')
	body_messages = [m for m in response.send_fnc.messages if m['type'] == 'http.response.body']
	assert len(body_messages) == 1

@pytest.mark.asyncio
async def testEmitBodyMoreBody():
	response = make_response()
	await emit_headers(response)
	await emit_body(response, b'chunk', more_body=True)

	assert response.body_sent == False  # still open
	await emit_body(response, b'final', more_body=False)
	assert response.body_sent == True

@pytest.mark.asyncio
async def testEmit():
	response = make_response()
	response.set_plain_text('ok')
	await emit(response)

	types = [m['type'] for m in response.send_fnc.messages]
	assert types == ['http.response.start', 'http.response.body']
	assert response.send_fnc.messages[1]['body'] == b'ok'

#-------------------------------------------------------------------------------

if __name__ == "__main__":
	testDefaults()
	testSetStatus()
	testSetStatusWithoutComplete()
	testAddHeader()
	testSetContent()
	testSetContentWithoutBody()
	testSetPlainText()
	testContentLengthIsByteCount()
	testAddCookie()
	testMethodChaining()
