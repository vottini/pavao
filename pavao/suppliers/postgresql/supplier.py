
import asyncio
import asyncpg
import pavao

database_schema = {
	"host": str,
	"port": 5432,
	"database": str,
	"user": str,
	"password": ""
}


class PostgresSupplier(pavao.ParameterSupplier):
	def __init__(self):
		self.pool = None
		self.enabled = False
		self.config = None


	def configure(self, loaded_settings):
		db_settings = loaded_settings.get_setting(
			"pavao.database.postgresql",
			database_schema)

		if db_settings is not None:
			self.config = db_settings
			self.enabled = True


	async def initialize(self):

		try:
			self.pool = await asyncpg.create_pool(**self.config)
			pavao.Logger.info("PostgreSQL database connected")

		except Exception as e:
			pavao.Logger.error("Error while setting up PostgreSQL database: " + str(e))
			raise pavao.PavaoException("Unable to start PostgreSQL database pool")


	def parameters_supplied(self):
		if not self.enabled:
			return dict()

		return {
			'pg_pool': [
				self.retrieve_pool,
				None
			],

			'db_connection': [
				self.create_connection,
				self.close_connection
			]
		}

	#------------------------------------------------------------

	async def retrieve_pool(self): return self.pool
	async def create_connection(self): return await self.pool.acquire()
	async def close_connection(self, conn): await self.pool.release(conn)

	#------------------------------------------------------------

	async def shutdown(self):
		if self.pool is not None:
			await self.pool.close()
			pavao.Logger.info("PostgreSQL database pool closed")
			self.pool = None

