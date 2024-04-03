
import datetime
import asyncio
import pavao

def proccess():
	validity = datetime.timedelta(days=5)
	success = pavao.refresh_token(validity)
	return "Success" if success else "Failure"


def pavao_task():

	return {
		'package': "Pavão",
		'name': "Refresh jwt secret key",
		'processor': proccess,
		'schedule': '0 0 * * *'
	}

