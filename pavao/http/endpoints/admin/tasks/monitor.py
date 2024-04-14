
import re
import asyncio
import pavao

from admin.common import localize_functionality

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
	try:
		task = path_variables["taskId"]

		sink = broadcasting.open_sink(f"taskState:{task}")
		cleanup = lambda : broadcasting.close_sink(sink)
		emit.on_disconnection(cleanup)
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

	except Exception as e:
		print(f"EXPCETION BRAVA: {e}")


async def pavao_endpoint(db_connection, persisted_settings):
	package_name, func_name = await localize_functionality("MONITOR_TASKS",
		db_connection, persisted_settings)

	return {
		'method': 'GET',
		'path': '/admin/tasks/{taskId:int}/monitor',
		'package': package_name,
		'functionality': func_name,
		'processor': process,
		'public': True
	}

