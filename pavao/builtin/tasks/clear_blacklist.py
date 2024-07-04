
import asyncio
import pavao

from tasks.common import localizer

async def proccess(server):
	removed = server.authorizer.clear_blacklist()
	yield f"{removed} expired tokens purged from blacklist"

def pavao_task():

	return {
		'package': "Pavão",
		'name': localizer.map("CLEAR_BLACKLIST"),
		'processor': proccess,
		'schedule': '0 0 * * *'
	}

