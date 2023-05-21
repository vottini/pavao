
import asyncpg
from .exception import PavaoException

_pool = None

async def close_database():
	global _pool
	if None != _pool:
		await _pool.close()
		_pool = None


async setup_database(host, port, database, user, password=None):
	await close_database()
	global _pool

	try:
		_pool = await asyncpg.create_pool(
			host=host, port=port, database=database,
			user=user, password=password)

	except Exception as e:
		print("Error while connecting to database: " + str(e))

	if None == _pool:
		msg = f"Unable to connect to database '{database}' at server '{host}:{port}'"
		raise PavaoException(msg)


def release_database(loop):
	loop.run_until_complete(close_database())

#-------------------------------------------------------------------------------

class DatabaseConnection:
	def __init__(self, pool):
		self.pool = pool
		self.conn = None

	async def __aenter__(self):
		self.conn = await self.pool.acquire()
		return self.conn

	async def __aexit__(self, *args):
		await self.pool.release(self.conn)


def database_connection():
	global _pool
	return DatabaseConnection(_pool)

#-------------------------------------------------------------------------------

__all__ = [
	"setup_database",
	"release_database",
	"database_connection"
]

