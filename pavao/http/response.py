
import asyncio
from .cookie import Cookie

class Response:
	def __init__(self, send_fnc):
		self.send_fnc = send_fnc

		self.status = 200
		self.cookies = dict()
		self.content_type = None
		self.content_length = None
		self.content = None

	def set_status(self, status):
		self.status = status
		return self

	def add_cookie(self, cookie):
		self.cookies[cookie.name] = cookie
		return self

	def set_plain_text(self, text):
		self.content = text.encode()
		self.content_type = b'text/plain'
		self.content_length = len(self.content)
		return self


async def emit(response):
	headers = list()

	if None != response.content_type:
		headers.append((b'content-type', response.content_type))

	if None != response.content_length:
		headers.append((b'content-length', str(response.content_length)))

	await response.send_fnc({
		'type': 'http.response.start',
		'status': response.status,
		'headers': headers
	})

	await response.send_fnc({
		'type': 'http.response.body',
		'body': response.content
	})

