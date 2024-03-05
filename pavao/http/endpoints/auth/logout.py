
import asyncio
import pavao

delete_refresh = pavao.include('queries/delete_refresh.sql')

async def process(handler, response, db_connection, auth_data):
	handler.authorizer.blacklist(auth_data)

	await db_connection.execute(
		delete_refresh,
		auth_data.account_id,
		auth_data.token)

	response.add_cookie(
		pavao.http.Cookie('token')
			.set_path('/refresh-token')
			.set_sameSite(pavao.http.SameSite.STRICT)
			.set_to_be_removed()
	)

	response.set_status(204)


def pavao_endpoint():
	return {
		'method': 'DELETE',
		'path': '/logout',
		'processor': process
	}

