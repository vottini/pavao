
import asyncio
import traceback

from ..logger import Logger


class LifespanHandler:
	def __init__(self, startup_callback, shutdown_callback):
		self.startup_callback = startup_callback
		self.shutdown_callback = shutdown_callback


	async def handle(self, scope, receive, send):

		message = await receive()
		while message['type'] != 'lifespan.startup':
			message = await receive()

		startup_succeeded = False
		try:
			await self.startup_callback()
			startup_succeeded = True
			await send({'type': 'lifespan.startup.complete'})

		except Exception as e:
			Logger.error(f"Exception occurred during startup: {e}")
			Logger.error(traceback.format_exc())

			try: await self.shutdown_callback()
			finally: await send({'type': 'lifespan.startup.failed'})

		message = await receive()
		while message['type'] != 'lifespan.shutdown':
			message = await receive()

		if not startup_succeeded:
			await send({'type': 'lifespan.shutdown.complete'})
			return

		try:
			await self.shutdown_callback()
			await send({'type': 'lifespan.shutdown.complete'})

		except Exception as e:
			Logger.error(f"Exception occurred during shutdown: {e}")
			Logger.error(traceback.format_exc())

			await send({'type': 'lifespan.shutdown.failed'})

#------------------------------------------------------------------------------

__all__ = [
	"LifespanHandler"
]

