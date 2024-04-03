
import asyncio
import pavao

purge_query = """

	WITH purged AS (
		DELETE FROM pavao.refresh_token
			WHERE expiration < NOW()
			RETURNING *)

	SELECT COUNT(*) FROM purged;

"""

async def proccess(db_pool):
	async with db_pool.connection() as connection:
		purged = await connection.fetchval(purge_query)
		return f"{purged} refresh token(s) purged"


def pavao_task():

	return {
		'package': "Pavão",
		'name': "Purges due refresh tokens",
		'processor': proccess,
		'schedule': '0 * * * *'
	}

