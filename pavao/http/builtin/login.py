
import asyncio
import asyncpg
import pavao

select_data_from_login = '''

	SELECT first_name, COALESCE(last_name, '')
		FROM pavao.account
		WHERE login = $1;

'''

login_blueprint = '''
	
	root {
		login: string (minLength=5, maxLength=32),
		password: string (minLength=8, maxLength=64)
	}

'''

#@pavao.json.generates
@pavao.acceptsJson(string=login_blueprint)
async def process(response, db_connection, parsed_json):
	login = parsed_json['login']

	row = await db_connection.fetchrow(
		select_data_from_login,
		login)

	if None == row:
		await asyncio.sleep(3)
		response.set_status(403)
		return

	response.set_plain_text(f"{row}")


def pavao_endpoint():
	return {
		'method': 'POST',
		'path': '/login',
		'processor': process,
		'public': True
	}

