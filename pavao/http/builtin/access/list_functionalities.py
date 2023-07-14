
import asyncio
import pavao

list_functionalities = pavao.include('list_functionalities.sql')

async def process(request, response, db_connection):
	handler.authorizer.blacklist(auth_data)
	await db_connection.execute(delete_refresh,
		auth_data.login, auth_data.token)

	response.add_cookie(
		pavao.http.Cookie('token')
			.set_path('/refresh-token')
			.set_to_be_removed()
	)


async def pavao_endpoint(parameters):
	localized_functionalities = pavao.include('functionalities.ini')

	localization = pavao.Localization(localized_functionalities)
	language = await parameters.get('language')
	functionality = localization.localize(language, "LIST_FUNCTIONALITIES")

	return {
		'method': 'GET',
		'path': '/admin/list_functionalities',
		'functionality': functionality,
		'processor': process
	}

