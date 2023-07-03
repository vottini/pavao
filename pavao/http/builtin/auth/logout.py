
import asyncio
import pavao

delete_refresh = pavao.include('delete_refresh.sql')

async def process(handler, request, response, db_connection, auth_data):
	handler.authorizer.blacklist(auth_data)
	await db_connection.execute(delete_refresh,
		auth_data.login, auth_data.token)


def pavao_endpoint():
	return {
		'method': 'DELETE',
		'path': '/logout',
		'processor': process
	}

