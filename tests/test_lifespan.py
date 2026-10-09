
import sys
sys.path.append('..')

import pytest
from unittest.mock import AsyncMock, patch

from pavao.lifespan.handler import LifespanHandler

#-------------------------------------------------------------------------------
# helpers

def make_receive(*message_types):
	messages = iter({'type': t} for t in message_types)
	return AsyncMock(side_effect=lambda: next(messages))


def make_handler(startup=None, shutdown=None):
	return LifespanHandler(
		startup_callback=startup or AsyncMock(),
		shutdown_callback=shutdown or AsyncMock()
	)

#-------------------------------------------------------------------------------
# happy path

@pytest.mark.asyncio
async def testHandleStartupCompleteOnSuccess():
	send = AsyncMock()
	handler = make_handler()
	receive = make_receive('lifespan.startup', 'lifespan.shutdown')

	await handler.handle({}, receive, send)

	sent = [c.args[0]['type'] for c in send.call_args_list]
	assert 'lifespan.startup.complete' in sent


@pytest.mark.asyncio
async def testHandleShutdownCompleteOnSuccess():
	send = AsyncMock()
	handler = make_handler()
	receive = make_receive('lifespan.startup', 'lifespan.shutdown')

	await handler.handle({}, receive, send)

	sent = [c.args[0]['type'] for c in send.call_args_list]
	assert 'lifespan.shutdown.complete' in sent


@pytest.mark.asyncio
async def testHandleCallsStartupThenShutdownCallbacks():
	order = []
	async def startup(): order.append('startup')
	async def shutdown(): order.append('shutdown')

	receive = make_receive('lifespan.startup', 'lifespan.shutdown')
	await LifespanHandler(startup, shutdown).handle({}, receive, AsyncMock())

	assert order == ['startup', 'shutdown']

#-------------------------------------------------------------------------------
# startup failure

@pytest.mark.asyncio
async def testHandleStartupFailedOnException():
	send = AsyncMock()
	startup = AsyncMock(side_effect=RuntimeError("boom"))
	handler = make_handler(startup=startup)
	receive = make_receive('lifespan.startup', 'lifespan.shutdown')

	with patch('pavao.lifespan.handler.Logger'), \
		 patch('pavao.lifespan.handler.traceback'):
		await handler.handle({}, receive, send)

	sent = [c.args[0]['type'] for c in send.call_args_list]
	assert 'lifespan.startup.failed' in sent
	assert 'lifespan.startup.complete' not in sent


@pytest.mark.asyncio
async def testHandleCallsShutdownOnStartupException():
	shutdown = AsyncMock()
	startup = AsyncMock(side_effect=RuntimeError("boom"))
	handler = make_handler(startup=startup, shutdown=shutdown)
	receive = make_receive('lifespan.startup', 'lifespan.shutdown')

	with patch('pavao.lifespan.handler.Logger'), \
		 patch('pavao.lifespan.handler.traceback'):
		await handler.handle({}, receive, send=AsyncMock())

	shutdown.assert_called_once()


@pytest.mark.asyncio
async def testHandleLogsStartupException():
	startup = AsyncMock(side_effect=RuntimeError("startup error"))
	handler = make_handler(startup=startup)
	receive = make_receive('lifespan.startup', 'lifespan.shutdown')

	with patch('pavao.lifespan.handler.Logger') as mock_logger, \
		 patch('pavao.lifespan.handler.traceback'):
		await handler.handle({}, receive, AsyncMock())

	mock_logger.error.assert_called()
	assert 'startup error' in mock_logger.error.call_args_list[0].args[0]

#-------------------------------------------------------------------------------
# double-shutdown prevention

@pytest.mark.asyncio
async def testHandleDoesNotCallShutdownTwiceAfterStartupFailure():
	shutdown = AsyncMock()
	startup = AsyncMock(side_effect=RuntimeError("boom"))
	handler = make_handler(startup=startup, shutdown=shutdown)
	receive = make_receive('lifespan.startup', 'lifespan.shutdown')

	with patch('pavao.lifespan.handler.Logger'), \
		 patch('pavao.lifespan.handler.traceback'):
		await handler.handle({}, receive, AsyncMock())

	assert shutdown.call_count == 1


@pytest.mark.asyncio
async def testHandleSendsShutdownCompleteEvenAfterStartupFailure():
	send = AsyncMock()
	startup = AsyncMock(side_effect=RuntimeError("boom"))
	handler = make_handler(startup=startup)
	receive = make_receive('lifespan.startup', 'lifespan.shutdown')

	with patch('pavao.lifespan.handler.Logger'), \
		 patch('pavao.lifespan.handler.traceback'):
		await handler.handle({}, receive, send)

	sent = [c.args[0]['type'] for c in send.call_args_list]
	assert 'lifespan.shutdown.complete' in sent

#-------------------------------------------------------------------------------
# shutdown failure

@pytest.mark.asyncio
async def testHandleShutdownFailedOnException():
	send = AsyncMock()
	shutdown = AsyncMock(side_effect=RuntimeError("shutdown boom"))
	handler = make_handler(shutdown=shutdown)
	receive = make_receive('lifespan.startup', 'lifespan.shutdown')

	with patch('pavao.lifespan.handler.Logger'), \
		 patch('pavao.lifespan.handler.traceback'):
		await handler.handle({}, receive, send)

	sent = [c.args[0]['type'] for c in send.call_args_list]
	assert 'lifespan.shutdown.failed' in sent
	assert 'lifespan.shutdown.complete' not in sent


@pytest.mark.asyncio
async def testHandleLogsShutdownException():
	shutdown = AsyncMock(side_effect=RuntimeError("shutdown error"))
	handler = make_handler(shutdown=shutdown)
	receive = make_receive('lifespan.startup', 'lifespan.shutdown')

	with patch('pavao.lifespan.handler.Logger') as mock_logger, \
		 patch('pavao.lifespan.handler.traceback'):
		await handler.handle({}, receive, AsyncMock())

	mock_logger.error.assert_called()
	assert 'shutdown error' in mock_logger.error.call_args_list[0].args[0]

#-------------------------------------------------------------------------------
# message loop skips unexpected types

@pytest.mark.asyncio
async def testHandleSkipsUnexpectedMessagesBeforeStartup():
	send = AsyncMock()
	handler = make_handler()
	receive = make_receive('lifespan.unknown', 'lifespan.startup', 'lifespan.shutdown')

	await handler.handle({}, receive, send)

	sent = [c.args[0]['type'] for c in send.call_args_list]
	assert 'lifespan.startup.complete' in sent


@pytest.mark.asyncio
async def testHandleSkipsUnexpectedMessagesBeforeShutdown():
	send = AsyncMock()
	handler = make_handler()
	receive = make_receive('lifespan.startup', 'lifespan.unknown', 'lifespan.shutdown')

	await handler.handle({}, receive, send)

	sent = [c.args[0]['type'] for c in send.call_args_list]
	assert 'lifespan.shutdown.complete' in sent

#-------------------------------------------------------------------------------

if __name__ == "__main__":
	pytest.main([__file__, "-v"])
