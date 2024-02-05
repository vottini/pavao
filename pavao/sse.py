
import asyncio
import functools
import inspect

from .http.response import emit_headers
from .http.response import emit_body

_EVENT_SEPARATOR = "\n".encode()
def do_nothing(): ...

class ServerEvent:
	def __init__(self, response):
		self.response = response
		self.response.set_content("text/event-stream")
		self.disconnection_callback = do_nothing
		self.headers_sent = False
		self.orderly_shutdown = False

	async def emit_fragment(self, content, more_body=True):
		newlined_content = f"{content}\n"
		await emit_body(self.response,
			newlined_content.encode(),
			more_body)

	async def certify_headers_sent(self):
		await emit_headers(self.response)
		self.headers_sent = True

	async def end_event(self):
		await emit_body(self.response,
			_EVENT_SEPARATOR,
			True)

	#------------------------------------------------------------

	async def headers(self, status=200, headers=None):
		if self.headers_sent:
			return

		if headers is not None:
			for field, value in headers:
				self.response.add_header(field, value)

		self.response.set_status(status)
		await self.certify_headers_sent()

	def on_disconnection(self, callback):
		self.disconnection_callback = callback

	async def event(self, event_type, data=None):
		await self.certify_headers_sent()

		if data is None:
			await self.emit_fragment(f"event: {event_type}")
			await self.end_event()
			return

		await self.emit_fragment(f"event: {event_type}")
		await self.emit_fragment(f"data: {data}")
		await self.end_event()

	async def message(self, data):
		await self.certify_headers_sent()
		await self.emit_fragment(f"data: {data}")
		await self.end_event()

#-------------------------------------------------------------------------------

def generates_sse(fnc):
	fnc_nargs = fnc.__code__.co_argcount
	fnc_lvars = fnc.__code__.co_varnames
	fnc_params = fnc_lvars[0:fnc_nargs]

	@functools.wraps(fnc)
	async def wrapped(
		handler,
		request,
		response,
		path_variables,
		db_connection,
		auth_data,
		receive):

		emit_instance = ServerEvent(response)

		all_args = {
			'handler': handler,
			'request': request,
			'emit': emit_instance,
			'path_variables': path_variables,
			'db_connection': db_connection,
			'auth_data': auth_data
		}

		selected_args = list()
		for param_name in fnc_params:
			selected_args.append(all_args[param_name])

		async def run_endpoint():
			await fnc(*selected_args)
			await emit_instance.emit_fragment("", False)
			emit_instance.orderly_shutdown = True

		async def monitor_disconnection():
			message = await receive()
			while message.get('type') != "http.disconnect":
				message = await receive()

			if not emit_instance.orderly_shutdown:
				fnc = emit_instance.disconnection_callback
				is_awaitable = inspect.iscoroutinefunction(fnc)
				await fnc() if is_awaitable else fnc()

		tasks = [
			asyncio.create_task(run_endpoint()),
			asyncio.create_task(monitor_disconnection()),
		]

		await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
		for task in tasks:
			task.cancel()

	return wrapped


#-------------------------------------------------------------------------------

__all__ = [
	"generates_sse"
]

