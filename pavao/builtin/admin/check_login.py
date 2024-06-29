
import re
import asyncio
import pavao

from admin.common import localizer
from admin.common import assert_admin_access

_allowed_pattern = re.compile(r'^[a-z][a-z0-9]*(?:.[a-z0-9]+)?$')
_count_login = "SELECT COUNT(*) FROM pavao.account WHERE login = $1;"

def valid_login(login):
	found = _allowed_pattern.search(login)
	return found is not None


@pavao.generates_json(string_blueprint="root bool")
async def process(request, response, db_connection):
	if not 'login' in request.params:
		response.set_status(400)
		return {"error": "Bad request"}

	candidate = request.params['login']
	if valid_login(candidate):
		count = await db_connection.fetchval(_count_login, candidate)
		return 0 == count

	return False


@assert_admin_access
def pavao_endpoint():

	return {
		'method': 'GET',
		'path': '/admin/check-login',
		'package': localizer.map("PACKAGE"),
		'functionality': localizer.map("CHECK_LOGIN"),
		'processor': process
	}

