
import os
import asyncio
import datetime
import aiosqlite
import sqlite3
import umapper
import pavao

from pavao.builtin.foundation.sqlite.task_store import SqliteTaskStore

config_schema = {
	"enabled": True,
	"persist": True,
	"filename": "pavao.db",
	"trace": False
}

queries_dir = pavao.path_to('database')
db_creation = [arq for arq in os.listdir(queries_dir) if arq.endswith('.sql')]
db_creation.sort()

#-------------------------------------------------------------------------------

def convert_datetime(val):
	return datetime.datetime.fromisoformat(
		val.decode())

aiosqlite.register_adapter(datetime.datetime, lambda val: val.isoformat())
aiosqlite.register_adapter(bool, lambda val: '1' if val else '0')
aiosqlite.register_converter('timestamp', convert_datetime)
aiosqlite.register_converter('bool', lambda val: val.decode() == '1')

#-------------------------------------------------------------------------------

pavao.from_module('persisted_settings').import_item('PersistedSettings')

class SqliteSupplier(pavao.ParameterSupplier):
	def __init__(self):
		self.connection = None
		self.specs = None


	def parameters_supplied(self):
		if not self.specs.enabled:
			return dict()

		async def provide_task_store():
			return SqliteTaskStore(self.connection)

		async def provide_stored_settings():
			return PersistedSettings(self.connection)

		return {
			'task_store': [provide_task_store, None],
			'stored_settings': [provide_stored_settings, None]
		}


	def configure(self, loaded_settings):
		db_settings = loaded_settings.get_setting(
			"pavao.database.sqlite",
			config_schema)

		self.specs = umapper.convert_to_object(db_settings)


	async def initialize(self):
		if not self.specs.enabled:
			return

		try:
			if not self.specs.persist:
				pavao.Logger.info("Pavao internal database set as not persistent")
				db_name = ':memory:'

			else: db_name = self.specs.filename
			self.connection = await aiosqlite.connect(db_name,
				detect_types=sqlite3.PARSE_DECLTYPES)

			if self.specs.trace:
				sqlite3.enable_callback_tracebacks(True)
				await self.connection.set_trace_callback(print)

			pavao.Logger.info("Pavao internal database connected")

			for query in db_creation:
				async with self.connection.cursor() as cursor:
					with open(os.path.join(queries_dir, query)) as fd:
						await cursor.executescript(fd.read())

		except Exception as e:
			pavao.Logger.error("Error while setting up internal database: " + str(e))
			raise pavao.PavaoException("Unable to setup internal Pavao database")

	#------------------------------------------------------------

	async def shutdown(self):
		if self.connection is not None:
			await self.connection.close()
			pavao.Logger.info("Pavao internal database connection closed")
			self.connection = None

