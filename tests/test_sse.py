
import sys
sys.path.append('..')

import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, call
from pavao.sse import ServerEvent
from pavao.broadcasting import SHUTDOWN_TOPIC

#-------------------------------------------------------------------------------

def make_response():
	res = MagicMock()
	res.headers = {}
	res.cookies = {}
	res.status = 200
	res.headers_sent = False
	res.body_sent = False
	res.send_fnc = AsyncMock()
	return res

def sent_bodies(response):
	return [
		c.args[0]['body'].decode()
		for c in response.send_fnc.call_args_list
		if c.args[0].get('type') == 'http.response.body'
	]

#-------------------------------------------------------------------------------
# ServerEvent construction

def testConstructorSetsContentType(make_response=None):
	res = make_response() if make_response else globals()['make_response']()
	se = ServerEvent(res)
	res.set_content.assert_called_once_with("text/event-stream")

def testConstructorHeadersNotSentYet():
	res = make_response()
	se = ServerEvent(res)
	assert not se.headers_sent

def testConstructorOrderlyShutdownFalse():
	res = make_response()
	se = ServerEvent(res)
	assert not se.orderly_shutdown

#-------------------------------------------------------------------------------
# headers

@pytest.mark.asyncio
async def testHeadersSendsStartEvent():
	res = make_response()
	se = ServerEvent(res)
	await se.headers()
	types = [c.args[0]['type'] for c in res.send_fnc.call_args_list]
	assert 'http.response.start' in types

@pytest.mark.asyncio
async def testHeadersSetsStatus():
	res = make_response()
	se = ServerEvent(res)
	await se.headers(status=201)
	res.set_status.assert_called_with(201)

@pytest.mark.asyncio
async def testHeadersIdempotent():
	res = make_response()
	se = ServerEvent(res)
	await se.headers()
	await se.headers()
	start_calls = [c for c in res.send_fnc.call_args_list
		if c.args[0].get('type') == 'http.response.start']
	assert len(start_calls) == 1

@pytest.mark.asyncio
async def testHeadersAddsCustomHeaders():
	res = make_response()
	se = ServerEvent(res)
	await se.headers(headers=[("X-Custom", "value")])
	res.add_header.assert_called_with("X-Custom", "value")

#-------------------------------------------------------------------------------
# message

@pytest.mark.asyncio
async def testMessageEmitsDataLine():
	res = make_response()
	se = ServerEvent(res)
	await se.message("hello")
	bodies = sent_bodies(res)
	assert any("data: hello" in b for b in bodies)

@pytest.mark.asyncio
async def testMessageEmitsSeparator():
	res = make_response()
	se = ServerEvent(res)
	await se.message("hello")
	bodies = sent_bodies(res)
	assert any(b == "\n" for b in bodies)

@pytest.mark.asyncio
async def testMessageSendsHeadersIfNotSent():
	res = make_response()
	se = ServerEvent(res)
	await se.message("hello")
	assert se.headers_sent

#-------------------------------------------------------------------------------
# event

@pytest.mark.asyncio
async def testEventEmitsEventLine():
	res = make_response()
	se = ServerEvent(res)
	await se.event("update", "payload")
	bodies = sent_bodies(res)
	assert any("event: update" in b for b in bodies)

@pytest.mark.asyncio
async def testEventEmitsDataLine():
	res = make_response()
	se = ServerEvent(res)
	await se.event("update", "payload")
	bodies = sent_bodies(res)
	assert any("data: payload" in b for b in bodies)

@pytest.mark.asyncio
async def testEventWithoutDataNoDataLine():
	res = make_response()
	se = ServerEvent(res)
	await se.event("ping")
	bodies = sent_bodies(res)
	assert not any("data:" in b for b in bodies)

@pytest.mark.asyncio
async def testEventEmitsSeparator():
	res = make_response()
	se = ServerEvent(res)
	await se.event("ping")
	bodies = sent_bodies(res)
	assert any(b == "\n" for b in bodies)

#-------------------------------------------------------------------------------
# on_disconnection callback

def testOnDisconnectionRegistersCallback():
	res = make_response()
	se = ServerEvent(res)
	cb = MagicMock()
	se.on_disconnection(cb)
	assert se.disconnection_callback is cb

#-------------------------------------------------------------------------------
# generates_sse wrapper — DI signature

def testWrappedFunctionDeclaresDIParams():
	from pavao.sse import generates_sse
	import pavao.utils as utils

	@generates_sse()
	async def endpoint(emit, response):
		pass

	params = utils.deduce_parameters(endpoint)
	assert "response" in params
	assert "receive" in params
	assert "broadcasting" in params

def testWrappedFunctionExcludesEmitFromSignature():
	from pavao.sse import generates_sse
	import pavao.utils as utils

	@generates_sse()
	async def endpoint(emit, response):
		pass

	params = utils.deduce_parameters(endpoint)
	assert "emit" not in params

#-------------------------------------------------------------------------------

if __name__ == "__main__":
	pytest.main([__file__, "-v"])
