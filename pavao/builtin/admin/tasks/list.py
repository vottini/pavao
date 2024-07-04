
import asyncio
import pavao

from admin.common import localizer
from admin.common import assert_admin_access

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
async def process(server, request):
	localization_priority = request.parse_locale_priority()
	grouped = dict()

	for task in server.scheduler.list_tasks(localization_priority):
		package = task['package']
		package_funcs = grouped.get(package, list())
		package_funcs.append(dict(task))
		grouped[package] = package_funcs

	return [
		{'package': package, 'tasks': tasks}
		for package, tasks in grouped.items()
	]


@assert_admin_access
def pavao_endpoint():

	return {
		'method': 'GET',
		'path': '/admin/tasks',
		'package': localizer.map("PACKAGE"),
		'functionality': localizer.map("LIST_TASKS"),
		'processor': process
	}

