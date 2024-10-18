
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


	@property
	def configured(self):
		return self.pool is not None


	async def init(self, loaded_settings):
		db_settings = loaded_settings.get_setting(
			"pavao.database.postgresql",
			_database_schema)

		if db_settings is None:
			pavao.Logger.info("PostgreSQL database not configured")
			return

		try:
			self.pool = await asyncpg.create_pool(**db_settings)
			pavao.Logger.info("PostgreSQL database connected")

		except Exception as e:
			pavao.Logger.error("Error while setting up PostgreSQL database: " + str(e))
			raise pavao.PavaoException("Unable to start PostgreSQL database pool")

	#------------------------------------------------------------

	async def create_connection(self):
		conn = await self.pool.acquire() if self.configured else None
		return conn


	async def close_connection(self, conn):
		if conn is not None:
			await self.pool.release(conn)

	#------------------------------------------------------------

	async def shutdown(self):
		if self.configured:
			await self.pool.close()
			pavao.Logger.info("PostgreSQL database pool closed")

