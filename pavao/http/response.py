
import asyncio
from .cookie import Cookie

class Response:
	def __init__(self, send_fnc):
		self.send_fnc = send_fnc
		self.content_type = None
		self.content = None
		self.cookies = dict()
		self.status = 200

	def set_status(self, status):
		self.status = status
		return self

	def add_cookie(self, cookie):
		self.cookies[cookie.name] = cookie
		return self

	def set_plain_text(self, text):
		self.content_type = b'text/plain'
		self.content = text.encode()
		return self


async def emit(response):
	headers = list()

	if None != response.content_type:
		headers.append((b'content-type', response.content_type))

	await response.send_fnc({
		'type': 'http.response.start',
		'status': response.status,
		'headers': headers
	})

	await response.send_fnc({
		'type': 'http.response.body',
		'body': response.content
	})

