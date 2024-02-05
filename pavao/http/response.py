
import asyncio
from .cookie import Cookie

class Response:
	def __init__(self, send_fnc):
		self.send_fnc = send_fnc
		self.headers_sent = False
		self.body_sent = False

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

	def set_content(self, content_type, content=None):
		self.headers['content-type'] = content_type

		if content is not None:
			self.headers['content-length'] = str(len(content))
			self.content = content

		return self

	def set_plain_text(self, text):
		self.set_content('text/plain', text.encode())

#-------------------------------------------------------------------------------

async def emit_headers(response):
	if response.headers_sent:
		return

	response.headers_sent = True
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


async def emit_body(response, content, more_body=False):
	if response.body_sent:
		return

	await response.send_fnc({
		'type': 'http.response.body',
		'body': content,
		'more_body': more_body
	})

	if not more_body:
		response.body_sent = True


async def emit(response):
	await emit_headers(response)
	await emit_body(response, response.content)

