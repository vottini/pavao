
import asyncio
import functools
import inspect

from .http.response import emit_headers
from .http.response import emit_body
from .broadcasting import SHUTDOWN_TOPIC

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

	async def _certify_headers_sent(self):
		await emit_headers(self.response)
		self.headers_sent = True

	async def end_event(self):
		await emit_body(self.response,
			_EVENT_SEPARATOR,
			True)

	#------------------------------------------------------------

	def on_disconnection(self, callback):
		self.disconnection_callback = callback


	async def headers(self, status=200, headers=None):
		if self.headers_sent:
			return

		if headers is not None:
			for field, value in headers:
				self.response.add_header(field, value)

		self.response.set_status(status)
		await self._certify_headers_sent()


	async def event(self, event_type, data=None):
		await self._certify_headers_sent()

		if data is None:
			await self.emit_fragment(f"event: {event_type}")
			await self.end_event()
			return

		await self.emit_fragment(f"event: {event_type}")
		await self.emit_fragment(f"data: {data}")
		await self.end_event()


	async def message(self, data):
		await self._certify_headers_sent()
		await self.emit_fragment(f"data: {data}")
		await self.end_event()

#-------------------------------------------------------------------------------

generates_sse_output = { "emit" }
generates_sse_params = { "receive", "response", "broadcasting" }
generates_sse_template = """

@functools.wraps(fnc)
async def wrapped({ALL_PARAMS}):
	emit_instance = ServerEvent(response)

	all_args = {{
		'emit': emit_instance,
		{CONTEXT}
	}}

	selected_args = list()
	for param_name in {FNC_PARAMS}:
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
			callback = emit_instance.disconnection_callback
			is_awaitable = inspect.iscoroutinefunction(callback)
			await callback() if is_awaitable else callback()

	async def monitor_shutdown():
		shutdown_sink = broadcasting.open_sink(SHUTDOWN_TOPIC)
		try:
			await shutdown_sink.get_message()
			await emit_instance.event("serverShutdown")
		finally:
			broadcasting.close_sink(shutdown_sink)

	tasks = [
		asyncio.create_task(run_endpoint()),
		asyncio.create_task(monitor_disconnection()),
		asyncio.create_task(monitor_shutdown()),
	]

	if send_heartbeats:
		async def heartbeat_sending():
			await asyncio.sleep(initial_heartbeat_delay_secs)
			await emit_instance.event("heartBeat")

			while True:
				await asyncio.sleep(heartbeat_interval_secs)
				await emit_instance.event("heartBeat")

		tasks.append(asyncio.create_task(heartbeat_sending()))

	await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
	for task in tasks: task.cancel()

"""

def generates_sse(
	send_heartbeats=True,
	initial_heartbeat_delay_secs=20,
	heartbeat_interval_secs=20):

	def wrapper(fnc):
		fnc_nargs = fnc.__code__.co_argcount
		fnc_lvars = fnc.__code__.co_varnames
		fnc_params = fnc_lvars[0:fnc_nargs]

		all_params = (
			(set(fnc_params) - generates_sse_output)
			| generates_sse_params
		)

		# exec is intentional: the DI system discovers injectable parameters by
		# reading co_varnames directly off the function object. A standard closure
		# or functools.wraps wrapper would expose the wrapper's own signature, not
		# the composed set needed after decoration. exec generates a function whose
		# co_varnames exactly match all_params, so DI introspection sees the right
		# parameters through arbitrarily deep decorator chains.
		code = generates_sse_template.format(
			ALL_PARAMS=','.join(all_params),
			CONTEXT=','.join(map(lambda x : f"'{x}': {x}", all_params)),
			FNC_PARAMS=str(fnc_params)
		)

		namespace = globals().copy()
		scope = locals().copy()

		namespace.update({
			'send_heartbeats': send_heartbeats,
			'initial_heartbeat_delay_secs': initial_heartbeat_delay_secs,
			'heartbeat_interval_secs': heartbeat_interval_secs,
			'fnc': fnc
		})

		exec(code, namespace, scope)
		return scope['wrapped']

	return wrapper

#-------------------------------------------------------------------------------

__all__ = [
	"generates_sse"
]

