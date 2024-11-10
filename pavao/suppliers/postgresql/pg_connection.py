
import asyncio
import asyncpg
import pavao

_database_schema = {
	"host": str,
	"port": 5432,
	"database": str,
	"user": str,
	"password": ""
}


class ConnectionSupplier(pavao.ParameterSupplier):
	def __init__(self):
		self.pool = None

	def parameters_supplied(self):
		return {
			'db_connection': [
				self.create_connection,
				self.close_connection
			]
		}


	async def init(self, loaded_settings):
		db_settings = loaded_settings.get_setting(
			"pavao.database.postgresql",
			_database_schema)

		if db_settings is None:
			pavao.Logger.info("PostgreSQL database not configured")
			return False

		try:
			self.pool = await asyncpg.create_pool(**db_settings)
			pavao.Logger.info("PostgreSQL database connected")
			return True

		except Exception as e:
			pavao.Logger.error("Error while setting up PostgreSQL database: " + str(e))
			raise pavao.PavaoException("Unable to start PostgreSQL database pool")

	#------------------------------------------------------------

	async def create_connection(self): return await self.pool.acquire()
	async def close_connection(self, conn): await self.pool.release(conn)

	#------------------------------------------------------------

	async def shutdown(self):
		if self.pool is not None:
			await self.pool.close()
			pavao.Logger.info("PostgreSQL database pool closed")
			self.pool = None

