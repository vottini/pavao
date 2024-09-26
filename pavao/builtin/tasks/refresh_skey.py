
import datetime
import asyncio
import pavao

from tasks.common import localizer

async def proccess():
	validity = datetime.timedelta(days=5)
	pavao.refresh_secret_key(validity)
	yield "Secret key refreshed"


def pavao_task(db_connection):
	if db_connection is None:
		return

	return {
		'package': "Pavão",
		'name': localizer.map("REFRESH_SECRET_KEY"),
		'processor': proccess,
		'schedule': '0 0 * * *'
	}

