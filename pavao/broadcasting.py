
import asyncio

SHUTDOWN_TOPIC = "PAVAO.SHUTDOWN"

class Sink:
	def __init__(self, topic):
		# maxsize=0 means unbounded; set a positive value to apply backpressure
		self.queue = asyncio.Queue()
		self.topic = topic

	async def get_message(self):
		msg = await self.queue.get()
		self.queue.task_done()
		return msg


class Broadcaster:
	def __init__(self):
		self.topics = dict()

	def open_sink(self, topic):
		sink = Sink(topic)
		topic_sinks = self.topics.get(topic, list())
		topic_sinks.append(sink)
		self.topics[topic] = topic_sinks
		return sink


	async def write_message(self, topic, message):
		if not topic in self.topics: return
		for sink in self.topics[topic]:
			await sink.queue.put(message)


	def close_sink(self, sink):
		topic_sinks = self.topics.get(sink.topic, list())

		filtered_sinks = [ snk
			for snk in topic_sinks
			if snk is not sink
		]

		if len(filtered_sinks) == 0:
			self.topics.pop(sink.topic, None)

		else:
			self.topics[sink.topic] = filtered_sinks


	async def announce_shutdown(self):
		await self.write_message(SHUTDOWN_TOPIC, None)


__all__ = [
	"SHUTDOWN_TOPIC",
	"Broadcaster",
]

