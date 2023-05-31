
import asyncio
import inspect

async def _secure_call(fnc):
	if fnc != None:
		if inspect.isawaitable(fnc):
			return await fnc()

		else:
			return fnc()


class LifespanHandler:
	def __init__(self, startup_callback=None, shutdown_callback=None):
		self.startup_callback = startup_callback
		self.shutdown_callback = shutdown_callback


	async def handle(self, scope, receive, send):
		message = await receive()

		if message['type'] == 'lifespan.startup':

			try:
				await _secure_call(self.startup_callback)
				await send({'type': 'lifespan.startup.complete'})

			except Exception as e:
				print(f"Exception occured during startup: {e}")
				await send({'type': 'lifespan.startup.failed'})

		elif message['type'] == 'lifespan.shutdown':

			try:
				await _secure_call(self.shutdown_callback)
				await send({'type': 'lifespan.shutdown.complete'})

			except Exception as e:
				print(f"Exception occured during shutdown: {e}")
				await send({'type': 'lifespan.shutdown.failed'})

#------------------------------------------------------------------------------

__all__ = [
	"LifespanHandler"
]

