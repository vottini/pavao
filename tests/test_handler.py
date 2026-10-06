
import sys
sys.path.append('..')

import pytest
from pavao.http.handler import HttpHandler
from pavao.registry import Registry
from pavao.endpoint import EndpointData

#-------------------------------------------------------------------------------

class Collector:
	def __init__(self):
		self.messages = []

	async def __call__(self, message):
		self.messages.append(message)

	def status(self):
		start = next(m for m in self.messages if m['type'] == 'http.response.start')
		return start['status']

	def headers(self):
		start = next(m for m in self.messages if m['type'] == 'http.response.start')
		return {k.decode(): v.decode() for k, v in start['headers']}


def make_scope(method='GET', path='/', headers=None, query_string=b''):
	return {
		'type': 'http',
		'method': method,
		'path': path,
		'query_string': query_string,
		'headers': headers or [],
		'server': ('127.0.0.1', 8000),
		'client': ('127.0.0.1', 12345),
	}

async def noop_receive():
	return {}

def make_handler():
	handler = HttpHandler(server=object(), broadcasting=object())
	return handler

def make_endpoint(fn):
	specs = {'method': 'GET', 'path': '/'}
	return EndpointData(fn, specs)

#-------------------------------------------------------------------------------

class MockSettings:
	def __init__(self, value):
		self._value = value

	def get_setting(self, key, schema):
		return self._value

#-------------------------------------------------------------------------------

@pytest.mark.asyncio
async def testInitLoadsCorsSettings():
	handler = make_handler()
	settings = MockSettings({
		'CORS': {
			'origins': ['https://example.com'],
			'headers': ['x-custom-header']
		}
	})
	await handler.init(settings)
	assert 'https://example.com' in handler.cors_origins
	assert 'x-custom-header' in handler.cors_headers

@pytest.mark.asyncio
async def testInitNoHttpSettings():
	handler = make_handler()
	await handler.init(MockSettings(None))
	assert handler.cors_origins == []

#-------------------------------------------------------------------------------

@pytest.mark.asyncio
async def testInactiveReturns503():
	handler = make_handler()
	handler.deactivate()

	send = Collector()
	await handler.handle(make_scope(), noop_receive, send)
	assert send.status() == 503

@pytest.mark.asyncio
async def testEndpointNotFound():
	handler = make_handler()

	send = Collector()
	await handler.handle(make_scope('GET', '/missing'), noop_receive, send)
	assert send.status() == 404

@pytest.mark.asyncio
async def testEndpointFound():
	handler = make_handler()

	called = []
	async def endpoint(ctx):
		called.append(ctx)
		ctx['response'].set_status(200)

	registry = Registry()
	registry.add_endpoint('GET', '/hello', make_endpoint(endpoint))
	await handler.update_registry(registry)

	send = Collector()
	await handler.handle(make_scope('GET', '/hello'), noop_receive, send)
	assert send.status() == 200
	assert len(called) == 1

@pytest.mark.asyncio
async def testEndpointContextContents():
	handler = make_handler()

	received_ctx = {}
	async def endpoint(ctx):
		received_ctx.update(ctx)

	registry = Registry()
	registry.add_endpoint('GET', '/ctx', make_endpoint(endpoint))
	await handler.update_registry(registry)

	await handler.handle(make_scope('GET', '/ctx'), noop_receive, Collector())
	assert 'request' in received_ctx
	assert 'response' in received_ctx
	assert 'path_variables' in received_ctx
	assert 'broadcasting' in received_ctx
	assert 'server' in received_ctx
	assert 'receive' in received_ctx

@pytest.mark.asyncio
async def testPathVariablesExtracted():
	handler = make_handler()

	captured = {}
	async def endpoint(ctx):
		captured.update(ctx['path_variables'])

	registry = Registry()
	registry.add_endpoint('GET', '/users/{id:int}', make_endpoint(endpoint))
	await handler.update_registry(registry)

	await handler.handle(make_scope('GET', '/users/42'), noop_receive, Collector())
	assert captured == {'id': 42}

@pytest.mark.asyncio
async def testEndpointExceptionReturns500():
	handler = make_handler()

	async def boom(ctx):
		raise RuntimeError("something broke")

	registry = Registry()
	registry.add_endpoint('GET', '/boom', make_endpoint(boom))
	await handler.update_registry(registry)

	send = Collector()
	await handler.handle(make_scope('GET', '/boom'), noop_receive, send)
	assert send.status() == 500

@pytest.mark.asyncio
async def testMalformedRequestReturns400():
	handler = make_handler()

	# null byte in query string is a RequestException → must return 400, not 500
	scope = make_scope('GET', '/any', query_string=b'file=%00etc%2Fpasswd')
	send = Collector()
	await handler.handle(scope, noop_receive, send)
	assert send.status() == 400

#-------------------------------------------------------------------------------

@pytest.mark.asyncio
async def testWrongMethodReturns405():
	handler = make_handler()

	async def endpoint(ctx): pass
	registry = Registry()
	registry.add_endpoint('GET', '/resource', make_endpoint(endpoint))
	await handler.update_registry(registry)

	send = Collector()
	await handler.handle(make_scope('DELETE', '/resource'), noop_receive, send)
	assert send.status() == 405
	assert 'GET' in send.headers()['allow']

@pytest.mark.asyncio
async def test405AllowHeaderListsAllMethods():
	handler = make_handler()

	async def endpoint(ctx): pass
	registry = Registry()
	registry.add_endpoint('GET', '/resource', make_endpoint(endpoint))
	registry.add_endpoint('POST', '/resource', make_endpoint(endpoint))
	await handler.update_registry(registry)

	send = Collector()
	await handler.handle(make_scope('DELETE', '/resource'), noop_receive, send)
	assert send.status() == 405
	allow = send.headers()['allow']
	assert 'GET' in allow
	assert 'POST' in allow
	assert 'HEAD' in allow  # HEAD exposed because GET exists

@pytest.mark.asyncio
async def testHeadRoutesToGet():
	handler = make_handler()

	async def endpoint(ctx):
		ctx['response'].set_plain_text('hello world')

	registry = Registry()
	registry.add_endpoint('GET', '/data', make_endpoint(endpoint))
	await handler.update_registry(registry)

	send = Collector()
	await handler.handle(make_scope('HEAD', '/data'), noop_receive, send)
	assert send.status() == 200

	body = next(m for m in send.messages if m['type'] == 'http.response.body')
	assert body['body'] == b""  # body stripped

	headers = send.headers()
	assert headers['content-type'] == 'text/plain; charset=utf-8'
	assert headers['content-length'] == str(len(b'hello world'))  # length preserved

@pytest.mark.asyncio
async def testHeadNotFoundWhenNoGet():
	handler = make_handler()

	async def endpoint(ctx): pass
	registry = Registry()
	registry.add_endpoint('POST', '/data', make_endpoint(endpoint))
	await handler.update_registry(registry)

	send = Collector()
	await handler.handle(make_scope('HEAD', '/data'), noop_receive, send)
	assert send.status() == 405  # POST exists, so 405 not 404

@pytest.mark.asyncio
async def testOptionsListsHeadWhenGetExists():
	handler = make_handler()

	async def endpoint(ctx): pass
	registry = Registry()
	registry.add_endpoint('GET', '/resource', make_endpoint(endpoint))
	await handler.update_registry(registry)

	send = Collector()
	await handler.handle(make_scope('OPTIONS', '/resource'), noop_receive, send)
	allow = send.headers()['access-control-allow-methods']
	assert 'GET' in allow
	assert 'HEAD' in allow

@pytest.mark.asyncio
async def testCorsCustomHeaderNormalisedToLowercase():
	handler = make_handler()
	settings = MockSettings({
		'CORS': {
			'origins': [],
			'headers': ['X-Custom-Header', 'Authorization'],
		}
	})
	await handler.init(settings)
	assert 'x-custom-header' in handler.cors_headers
	assert 'authorization' in handler.cors_headers
	assert 'X-Custom-Header' not in handler.cors_headers

#-------------------------------------------------------------------------------

@pytest.mark.asyncio
async def testOptionsFoundMethods():
	handler = make_handler()

	async def endpoint(ctx): pass

	registry = Registry()
	registry.add_endpoint('GET', '/resource', make_endpoint(endpoint))
	registry.add_endpoint('POST', '/resource', make_endpoint(endpoint))
	await handler.update_registry(registry)

	send = Collector()
	await handler.handle(make_scope('OPTIONS', '/resource'), noop_receive, send)
	assert send.status() == 200
	allow = send.headers()['access-control-allow-methods']
	assert 'GET' in allow
	assert 'POST' in allow

@pytest.mark.asyncio
async def testOptionsNotFound():
	handler = make_handler()

	send = Collector()
	await handler.handle(make_scope('OPTIONS', '/nowhere'), noop_receive, send)
	assert send.status() == 404

@pytest.mark.asyncio
async def testOptionsAllowedHeaders():
	handler = make_handler()

	async def endpoint(ctx): pass
	registry = Registry()
	registry.add_endpoint('POST', '/data', make_endpoint(endpoint))
	await handler.update_registry(registry)

	headers = [
		(b'access-control-request-method', b'POST'),
		(b'access-control-request-headers', b'content-type, authorization'),
	]
	send = Collector()
	await handler.handle(make_scope('OPTIONS', '/data', headers=headers), noop_receive, send)
	allowed = send.headers()['access-control-allow-headers']
	assert 'content-type' in allowed
	assert 'authorization' in allowed

@pytest.mark.asyncio
async def testOptionsUnknownHeadersFiltered():
	handler = make_handler()

	async def endpoint(ctx): pass
	registry = Registry()
	registry.add_endpoint('GET', '/data', make_endpoint(endpoint))
	await handler.update_registry(registry)

	headers = [
		(b'access-control-request-headers', b'x-evil-header'),
	]
	send = Collector()
	await handler.handle(make_scope('OPTIONS', '/data', headers=headers), noop_receive, send)
	assert 'access-control-allow-headers' not in send.headers()

#-------------------------------------------------------------------------------

@pytest.mark.asyncio
async def testCorsMatchingOriginAdded():
	handler = make_handler()
	handler.cors_origins = ['https://example.com']

	async def endpoint(ctx): pass
	registry = Registry()
	registry.add_endpoint('GET', '/api', make_endpoint(endpoint))
	await handler.update_registry(registry)

	headers = [(b'origin', b'https://example.com')]
	send = Collector()
	await handler.handle(make_scope('GET', '/api', headers=headers), noop_receive, send)
	assert send.headers().get('access-control-allow-origin') == 'https://example.com'

@pytest.mark.asyncio
async def testCorsCredentialsNotSentByDefault():
	handler = make_handler()
	handler.cors_origins = ['https://example.com']

	async def endpoint(ctx): pass
	registry = Registry()
	registry.add_endpoint('GET', '/api', make_endpoint(endpoint))
	await handler.update_registry(registry)

	headers = [(b'origin', b'https://example.com')]
	send = Collector()
	await handler.handle(make_scope('GET', '/api', headers=headers), noop_receive, send)
	assert 'access-control-allow-credentials' not in send.headers()

@pytest.mark.asyncio
async def testCorsCredentialsSentWhenEnabled():
	handler = make_handler()
	handler.cors_origins = ['https://example.com']
	handler.cors_credentials = True

	async def endpoint(ctx): pass
	registry = Registry()
	registry.add_endpoint('GET', '/api', make_endpoint(endpoint))
	await handler.update_registry(registry)

	headers = [(b'origin', b'https://example.com')]
	send = Collector()
	await handler.handle(make_scope('GET', '/api', headers=headers), noop_receive, send)
	assert send.headers().get('access-control-allow-credentials') == 'true'

@pytest.mark.asyncio
async def testCorsVaryOriginAlwaysSet():
	handler = make_handler()
	handler.cors_origins = ['https://example.com']

	async def endpoint(ctx): pass
	registry = Registry()
	registry.add_endpoint('GET', '/api', make_endpoint(endpoint))
	await handler.update_registry(registry)

	# Vary: Origin must be set even when the origin doesn't match,
	# so caches don't serve a stale response to a different origin
	for origin in [b'https://example.com', b'https://other.com']:
		headers = [(b'origin', origin)]
		send = Collector()
		await handler.handle(make_scope('GET', '/api', headers=headers), noop_receive, send)
		assert send.headers().get('vary') == 'Origin'

@pytest.mark.asyncio
async def testCorsVaryNotSetWithoutOriginHeader():
	handler = make_handler()
	handler.cors_origins = ['https://example.com']

	async def endpoint(ctx): pass
	registry = Registry()
	registry.add_endpoint('GET', '/api', make_endpoint(endpoint))
	await handler.update_registry(registry)

	send = Collector()
	await handler.handle(make_scope('GET', '/api'), noop_receive, send)
	assert 'vary' not in send.headers()

@pytest.mark.asyncio
async def testCorsNonMatchingOriginNotAdded():
	handler = make_handler()
	handler.cors_origins = ['https://example.com']

	async def endpoint(ctx): pass
	registry = Registry()
	registry.add_endpoint('GET', '/api', make_endpoint(endpoint))
	await handler.update_registry(registry)

	headers = [(b'origin', b'https://evil.com')]
	send = Collector()
	await handler.handle(make_scope('GET', '/api', headers=headers), noop_receive, send)
	assert 'access-control-allow-origin' not in send.headers()

@pytest.mark.asyncio
async def testCorsNoOriginHeader():
	handler = make_handler()
	handler.cors_origins = ['https://example.com']

	async def endpoint(ctx): pass
	registry = Registry()
	registry.add_endpoint('GET', '/api', make_endpoint(endpoint))
	await handler.update_registry(registry)

	send = Collector()
	await handler.handle(make_scope('GET', '/api'), noop_receive, send)
	assert 'access-control-allow-origin' not in send.headers()

@pytest.mark.asyncio
async def testOptionsMaxAgeInPreflight():
	handler = make_handler()
	handler.cors_max_age = 300

	async def endpoint(ctx): pass
	registry = Registry()
	registry.add_endpoint('GET', '/api', make_endpoint(endpoint))
	await handler.update_registry(registry)

	send = Collector()
	await handler.handle(make_scope('OPTIONS', '/api'), noop_receive, send)
	assert send.headers().get('access-control-max-age') == '300'

@pytest.mark.asyncio
async def testInitLoadsCorsCredentialsAndMaxAge():
	handler = make_handler()
	settings = MockSettings({
		'CORS': {
			'origins': ['https://example.com'],
			'headers': [],
			'credentials': True,
			'max_age': 1800,
		}
	})
	await handler.init(settings)
	assert handler.cors_credentials == True
	assert handler.cors_max_age == 1800

#-------------------------------------------------------------------------------

if __name__ == "__main__":
	import asyncio
	asyncio.run(testInactiveReturns503())
	asyncio.run(testEndpointNotFound())
	asyncio.run(testEndpointFound())
	asyncio.run(testEndpointContextContents())
	asyncio.run(testPathVariablesExtracted())
	asyncio.run(testEndpointExceptionReturns500())
	asyncio.run(testMalformedRequestReturns400())
	asyncio.run(testOptionsFoundMethods())
	asyncio.run(testOptionsNotFound())
	asyncio.run(testOptionsAllowedHeaders())
	asyncio.run(testOptionsUnknownHeadersFiltered())
	asyncio.run(testCorsMatchingOriginAdded())
	asyncio.run(testCorsNonMatchingOriginNotAdded())
	asyncio.run(testCorsNoOriginHeader())
