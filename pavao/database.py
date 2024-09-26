
import os
import asyncio
import asyncpg

from .logger import Logger
from .exception import PavaoException
class DatabaseException(PavaoException):
	pass


_database_schema = {
	"host": str,
	"port": 5432,
	"database": str,
	"user": str,
	"password": ""
}


class DatabasePool:
	def __init__(self):
		self.pool = None

	async def setup(self, settings):
		await self.close()

		db_settings = settings.get_setting(
			"pavao.database",
			_database_schema)

		self.pool = None
		if db_settings is None:
			return

		try:
			self.pool = await asyncpg.create_pool(**db_settings)
			Logger.info("Database pool connected")

		except Exception as e:
			Logger.error("Error while setting up database: " + str(e))
			raise DatabaseException("Unable to start database pool")


	@property
	def configured(self):
		return self.pool is not None


	async def close(self):
		if self.configured:
			await self.pool.close()
			Logger.info("Database pool closed")
			self.pool = None

	#-------------------------------------------------------------------------------

	class ValidConnection:
		def __init__(self, pool):
			self.pool = pool
			self.conn = None

		async def __aenter__(self):
			self.conn = await self.pool.acquire()
			return self.conn

		async def __aexit__(self, *args):
			await self.pool.release(self.conn)


	class NullConnection:
		async def __aenter__(self): return None
		async def __aexit__(self, *args): ...


	def connection(self):
		return (
			DatabasePool.ValidConnection(self.pool) if self.configured
			else DatabasePool.NullConnection()
		)

#-------------------------------------------------------------------------------

__all__ = [
	"DatabaseException",
	"DatabasePool"
]

