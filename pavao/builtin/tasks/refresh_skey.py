
import datetime
import asyncio
import pavao

async def proccess():
	validity = datetime.timedelta(days=5)
	pavao.refresh_secret_key(validity)
	yield "Secret key refreshed"


def pavao_task():

	return {
		'package': "Pavão",
		'name': "Refresh jwt secret key",
		'processor': proccess,
		'schedule': '0 0 * * *'
	}

