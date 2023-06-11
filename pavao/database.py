
import asyncio
import asyncpg

from .logger import Logger
from .exception import PavaoException
class DatabaseException(PavaoException):
	pass

_database_schema = {
	"host": str,
	"database": str,
	"user": str,
	"port": 5432,
	"password": ""
}

class DatabasePool:
	def __init__(self):
		self.pool = None

	async def setup(self, settings):
		await self.close()

		try:
			db_settings = settings.getSetting("pavao.database", _database_schema)
			self.pool = await asyncpg.create_pool(**db_settings)
			Logger.info("Database pool connected")

		except Exception as e:
			Logger.error("Error while setting up database: " + str(e))
			raise DatabaseException("Unable to start database pool")


	async def close(self):
		if None != self.pool:
			await self.pool.close()
			Logger.info("Database pool closed")
			self.pool = None

	#-------------------------------------------------------------------------------
	
	class DatabaseConnection:
		def __init__(self, dbManager):
			self.pool = dbManager.pool
			self.conn = None
	
		async def __aenter__(self):
			self.conn = await self.pool.acquire()
			return self.conn
	
		async def __aexit__(self, *args):
			await self.pool.release(self.conn)
	
	
	def connection():
		return DatabaseConnection(_pool)

#-------------------------------------------------------------------------------

__all__ = [
	"DatabaseException",
	"DatabasePool"
]

