
import re
import asyncio
import pavao

from admin.common import localizer
from admin.common import assert_admin_access

atomic_messages = {
	'STARTED': 'taskStart',
	'FINISHED': 'taskEnded',
	'DISABLED': 'taskDisabled'
}


parametered_messages = {
	'taskOutput': re.compile(r"OUTPUT:(.*)"),
	'taskSchedule': re.compile(r"SCHEDULE:(.*)"),
	'taskEnabled': re.compile(r"ENABLED:(.*)")
}


@pavao.generates_sse(heartbeat_interval_secs=25)
async def process(broadcasting, path_variables, emit):
	task = path_variables["taskId"]

	sink = broadcasting.open_sink(f"taskState:{task}")
	emit.on_disconnection(lambda : broadcasting.close_sink(sink))
	await emit.headers()

	while True:
		msg = await sink.get_message()
		if msg in atomic_messages:
			event_type = atomic_messages[msg]
			await emit.event(event_type)
			continue

		for event, pattern in parametered_messages.items():
			if (match := pattern.match(msg)) is not None:
				await emit.event(event, match.groups()[0])
				continue


@assert_admin_access
def pavao_endpoint():

	return {
		'method': 'GET',
		'path': '/admin/tasks/{taskId:int}/monitor',
		'package': localizer.map("PACKAGE"),
		'functionality': localizer.map("MONITOR_TASKS"),
		'processor': process
	}

