
import os
import asyncio
import datetime
import aiosqlite
import pavao

_database_info = {
	"filename": "pavao.db"
}

queries_dir = pavao.path_to('database')
db_creation = [arq for arq in os.listdir(queries_dir) if arq.endswith('.sql')]
db_creation.sort()

#-------------------------------------------------------------------------------

def convert_datetime(val):
	decoded = val.decode()
	return datetime.datetime.fromisoformat(decoded)

aiosqlite.register_adapter(datetime.datetime, lambda val: val.isoformat())
aiosqlite.register_adapter(bool, lambda val: 'true' if val else 'false')

aiosqlite.register_converter('timestamp', convert_datetime)
aiosqlite.register_converter('bool', lambda val: val.decode() == 'true')

#-------------------------------------------------------------------------------

class SqlConnectionSupplier(pavao.ParameterSupplier):
	def __init__(self):
		self.connection = None


	def parameters_supplied(self):
		return {
			'sqlite_cursor': [
				self.create_cursor,
				self.close_cursor
			]
		}


	async def init(self, loaded_settings):
		db_settings = loaded_settings.get_setting(
			"pavao.database.sqlite",
			_database_info)

		try:
			self.connection = await aiosqlite.connect(db_settings['filename'])
			pavao.Logger.info("Pavao internal database connected")

			async with self.connection.cursor() as cursor:
				for query in db_creation:
					with open(os.path.join(queries_dir, query)) as fd:
						await cursor.execute(fd.read())

			return True

		except Exception as e:
			pavao.Logger.error("Error while setting up internal database: " + str(e))
			raise pavao.PavaoException("Unable to connect to internal Pavao database")

	#------------------------------------------------------------

	async def create_cursor(self): return await self.connection.cursor()
	async def close_cursor(self, conn): await conn.close()

	#------------------------------------------------------------

	async def shutdown(self):
		if self.connection is not None:
			await self.connection.close()
			pavao.Logger.info("Pavao internal database connection closed")
			self.connection = None

