
import asyncio
import pavao

async def proccess(server):
	removed = server.authorizer.clear_blacklist()
	yield f"{removed} expired tokens purged from blacklist"


def pavao_task():

	return {
		'package': "Pavão",
		'name': "Clear blacklist from expired entries",
		'processor': proccess,
		'schedule': '0 0 * * *'
	}

