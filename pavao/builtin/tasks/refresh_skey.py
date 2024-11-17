
import datetime
import asyncio
import pavao

from tasks.common import localizer

async def proccess(authorizer):
	validity = datetime.timedelta(days=5)
	authorizer.refresh_secret_key(validity)
	yield "Secret key refreshed"


#@pavao.enabled_case(
#	"configuration": "pavao.auth.enabled",
#	"parameters": ['authorizer']
#)
def pavao_task():

	return {
		'package': "Pavão",
		'name': localizer.map("REFRESH_SECRET_KEY"),
		'processor': proccess,
		'schedule': '0 0 * * *'
	}

