
import asyncio

from .request import *
from .registry import *
from .token import *

class HttpHandler:
	def __init__(self):
		self.registry = Registry()


	def set_registry(self, registry):
		self.registry = registry


	async def handle(self, scope, receive, send):
		print(f"SCOPE = {scope}")

		try:
			request = Request(scope)
			print(f"REQUEST {request}")

		except Exception as e:
			print(f"ERROR WAS {e}")

		await send({
			'type': 'http.response.start',
			'status': 200,
			'headers': [
				[b'content-type', b'text/plain'],
			]
		})

		await send({
			'type': 'http.response.body',
			'body': b'Hello, world!',
		})

