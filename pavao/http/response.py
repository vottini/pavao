
import asyncio
from .cookie import Cookie

class Response:
	def __init__(self, send_fnc):
		self.send_fnc = send_fnc

		self.status = 200
		self.headers = dict()
		self.cookies = dict()
		self.content = b""

	def set_status(self, status):
		self.status = status
		return self

	def add_cookie(self, cookie):
		self.cookies[cookie.get_identifier()] = cookie
		return self

	def add_header(self, header_name, header_value):
		self.headers[header_name] = header_value
		return self

	def set_content(self, content_type, content):
		self.content = content
		self.headers['content-type'] = content_type
		self.headers['content-length'] = str(len(content))
		return self


async def emit(response):
	sent_headers = list()
	for header_name, header_value in response.headers.items():
		sent_headers.append((
			header_name.encode(),
			header_value.encode()
		))

	for cookie in response.cookies.values():
		sent_headers.append((b'set-cookie', str(cookie).encode()))

	await response.send_fnc({
		'type': 'http.response.start',
		'status': response.status,
		'headers': sent_headers
	})

	await response.send_fnc({
		'type': 'http.response.body',
		'body': response.content
	})

