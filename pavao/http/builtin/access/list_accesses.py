
import asyncio
import pavao

from access.registering import localize_functionality

list_accesses = """

	SELECT cls.id, cls.name, func.id, func.name FROM pavao.access acs
		INNER JOIN pavao.class cls ON acs.cls = cls.id 
		INNER JOIN pavao.functionality func ON acs.functionality = func.id
		WHERE cls.admin;

"""

accesses_blueprint = """

	root {
		id: integer,
		name: string,

		functionalities: {
			id: integer,
			name: string
		} []
	} []

"""

@pavao.generatesJson(string=accesses_blueprint)
async def process(request, db_connection):
	accesses = await db_connection.fetch(list_accesses)
	classes = dict()

	for row in accesses:
		classId, className, *funcData = row
		entry = classes.get(classId, (classId, className, list()))
		entry[2].append(funcData)
		classes[classId] = entry
	
	result = list()
	for value in classes.values():
		funcs = [{'id': funcData[0], 'name': funcData[1]} for funcData in value[2]]
		entry = {'id': value[0], 'name': value[1], 'functionalities': funcs}
		result.append(entry)

	return result


async def pavao_endpoint(db_connection, parameters):
	func_name = await localize_functionality("LIST_ACCESSES",
		db_connection, parameters)

	return {
		'method': 'GET',
		'path': '/access/accesses',
		'functionality': func_name,
		'processor': process
	}

