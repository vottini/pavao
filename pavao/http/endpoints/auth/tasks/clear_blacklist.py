
import asyncio
import pavao

async def proccess(server):
	removed = server.authorizer.clear_blacklist()
	yield f"Blacklist cleared from {removed} tokens"


def pavao_task():

	return {
		'package': "Pavão",
		'name': "Clear blacklist from expired entries",
		'processor': proccess,
		'schedule': '0 0 * * *'
	}

