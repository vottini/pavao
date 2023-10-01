
import re
import asyncio
import pavao

from admin.common import localize_functionality

_allowed_pattern = re.compile(r'^[a-z][a-z0-9]*(?:.[a-z0-9]+)?$')
_count_login = "SELECT COUNT(*) FROM pavao.account WHERE login = $1;"

def valid_login(login):
	found = _allowed_pattern.search(login)
	return found is not None

@pavao.generatesJson(stringBlueprint="root bool")
async def process(request, response, db_connection):
	if not 'login' in request.params:
		response.set_status(400)
		return {"error": "Bad request"}

	candidate = request.params['login']
	if valid_login(candidate):
		count = await db_connection.fetchval(_count_login, candidate)
		return 0 == count

	return False

async def pavao_endpoint(db_connection, parameters):
	func_name = await localize_functionality("CHECK_LOGIN",
		db_connection, parameters)

	return {
		'method': 'GET',
		'path': '/admin/check-login',
		'functionality': func_name,
		'processor': process
	}

