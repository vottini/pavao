
import sys
sys.path.append('..')

import asyncio
import pytest
from pavao.broadcasting import Broadcaster, SHUTDOWN_TOPIC

#-------------------------------------------------------------------------------

@pytest.fixture
def broadcaster():
	return Broadcaster()

#-------------------------------------------------------------------------------
# open_sink / close_sink

def testOpenSinkRegistered(broadcaster):
	sink = broadcaster.open_sink("topic")
	assert "topic" in broadcaster.topics
	assert sink in broadcaster.topics["topic"]

def testOpenTwoSinksSameTopic(broadcaster):
	s1 = broadcaster.open_sink("topic")
	s2 = broadcaster.open_sink("topic")
	assert len(broadcaster.topics["topic"]) == 2

def testCloseSinkRemovesIt(broadcaster):
	sink = broadcaster.open_sink("topic")
	broadcaster.close_sink(sink)
	assert "topic" not in broadcaster.topics

def testCloseSinkKeepsOtherSinks(broadcaster):
	s1 = broadcaster.open_sink("topic")
	s2 = broadcaster.open_sink("topic")
	broadcaster.close_sink(s1)
	assert s2 in broadcaster.topics["topic"]
	assert s1 not in broadcaster.topics["topic"]

def testCloseSinkIdempotent(broadcaster):
	sink = broadcaster.open_sink("topic")
	broadcaster.close_sink(sink)
	broadcaster.close_sink(sink)  # must not raise

def testCloseSinkLastRemovesTopic(broadcaster):
	s1 = broadcaster.open_sink("topic")
	s2 = broadcaster.open_sink("topic")
	broadcaster.close_sink(s1)
	broadcaster.close_sink(s2)
	assert "topic" not in broadcaster.topics

#-------------------------------------------------------------------------------
# write_message

@pytest.mark.asyncio
async def testWriteMessageDeliveredToSink(broadcaster):
	sink = broadcaster.open_sink("topic")
	await broadcaster.write_message("topic", "hello")
	msg = await sink.get_message()
	assert msg == "hello"

@pytest.mark.asyncio
async def testWriteMessageDeliveredToAllSinks(broadcaster):
	s1 = broadcaster.open_sink("topic")
	s2 = broadcaster.open_sink("topic")
	await broadcaster.write_message("topic", "hello")
	assert await s1.get_message() == "hello"
	assert await s2.get_message() == "hello"

@pytest.mark.asyncio
async def testWriteMessageUnknownTopicIsNoop(broadcaster):
	await broadcaster.write_message("nonexistent", "hello")  # must not raise

@pytest.mark.asyncio
async def testWriteMessageDoesNotCrossTopics(broadcaster):
	s1 = broadcaster.open_sink("topic.a")
	s2 = broadcaster.open_sink("topic.b")
	await broadcaster.write_message("topic.a", "only-a")
	assert await s1.get_message() == "only-a"
	assert s2.queue.empty()

@pytest.mark.asyncio
async def testWriteMultipleMessagesOrdered(broadcaster):
	sink = broadcaster.open_sink("topic")
	for i in range(5):
		await broadcaster.write_message("topic", i)
	for i in range(5):
		assert await sink.get_message() == i

#-------------------------------------------------------------------------------
# announce_shutdown

@pytest.mark.asyncio
async def testAnnounceShutdownSendsNoneOnShutdownTopic(broadcaster):
	sink = broadcaster.open_sink(SHUTDOWN_TOPIC)
	await broadcaster.announce_shutdown()
	msg = await sink.get_message()
	assert msg is None

@pytest.mark.asyncio
async def testAnnounceShutdownDoesNotAffectOtherTopics(broadcaster):
	sink = broadcaster.open_sink("my.topic")
	await broadcaster.announce_shutdown()
	assert sink.queue.empty()

@pytest.mark.asyncio
async def testAnnounceShutdownNoSubscribersIsNoop(broadcaster):
	await broadcaster.announce_shutdown()  # must not raise

#-------------------------------------------------------------------------------

if __name__ == "__main__":
	pytest.main([__file__, "-v"])
