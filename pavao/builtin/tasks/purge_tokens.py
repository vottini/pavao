
import asyncio
import pavao

from tasks.common import localizer

purge_query = """

	WITH purged AS (
		DELETE FROM pavao.refresh_token
			WHERE expiration < NOW()
			RETURNING *)

	SELECT COUNT(*) FROM purged;

"""

async def proccess(db_connection):
	purged = await connection.fetchval(purge_query)
	yield f"{purged} refresh token(s) purged"


def pavao_task():

	return {
		'package': "Pavão",
		'name': localizer.map("PURGE_EXPIRED_TOKENS"),
		'processor': proccess,
		'schedule': '0 * * * *'
	}

