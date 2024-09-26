
import asyncio
import inspect
import traceback

from ..logger import Logger

async def _secure_call(fnc):
	if fnc is not None:
		if inspect.iscoroutinefunction(fnc): return await fnc()
		else: return fnc()


class LifespanHandler:
	def __init__(self, startup_callback=None, shutdown_callback=None):
		self.startup_callback = startup_callback
		self.shutdown_callback = shutdown_callback


	async def handle(self, scope, receive, send):

		message = await receive()
		while message['type'] != 'lifespan.startup':
			message = await receive()

		try:
			success = await _secure_call(self.startup_callback)
			response_event = 'lifespan.startup.complete' if success else 'lifespan.startup.failed'
			await send({'type': response_event})

		except Exception as e:
			Logger.error(f"Exception occured during startup: {e}")
			print(traceback.format_exc())

			try: await _secure_call(self.shutdown_callback)
			finally: await send({'type': 'lifespan.startup.failed'})

		message = await receive()
		while message['type'] != 'lifespan.shutdown':
			message = await receive()

		try:
			await _secure_call(self.shutdown_callback)
			await send({'type': 'lifespan.shutdown.complete'})

		except Exception as e:
			Logger.error(f"Exception occured during shutdown: {e}")
			print(traceback.format_exc())

			await send({'type': 'lifespan.shutdown.failed'})

#------------------------------------------------------------------------------

__all__ = [
	"LifespanHandler"
]

