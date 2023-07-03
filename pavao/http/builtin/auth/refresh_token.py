
import asyncio
import pavao

@pavao.generatesJson(string=output_blueprint)
async def process(request, response, db_connection):
	pass


def pavao_endpoint():
	return {
		'method': 'GET',
		'path': '/refresh-token',
		'processor': process,
		'public': True
	}

