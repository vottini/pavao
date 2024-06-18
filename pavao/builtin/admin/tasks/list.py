
import asyncio
import pavao

tasks_list = """

	root {
		package: string,
		tasks: {
			id: integer,
			name: string,
			enabled: bool
		} []
	} []

"""

@pavao.generates_json(string_blueprint=tasks_list)
async def process(server):
	grouped = dict()

	for task in server.scheduler.list_tasks():
		package = task['package']
		package_funcs = grouped.get(package, list())
		package_funcs.append(dict(task))
		grouped[package] = package_funcs

	return [
		{'package': package, 'tasks': tasks}
		for package, tasks in grouped.items()
	]


from admin.common import localize_functionality
async def pavao_endpoint(db_connection, persisted_settings):
	package_name, func_name = await localize_functionality("LIST_TASKS",
		db_connection, persisted_settings)

	return {
		'method': 'GET',
		'path': '/admin/tasks',
		'package': package_name,
		'functionality': func_name,
		'processor': process
	}

