
import os

from .. import database
from .. import properties

script_path = os.path.dirname(os.path.realpath(__file__))
localization_dir = os.path.join(script_path, "localization")
tables_dir = os.path.join(script_path, "tables")


set_language_query = """

	INSERT INTO pavao.parameters (name, type, value)
		VALUES ('language', 'str', $1)
		ON CONFLICT (name) DO UPDATE
			SET value = EXCLUDED.value;

"""

async def execute(settings, localization):
	localization_file = os.path.join(localization_dir, f"{localization}.ini")
	localization_specs = properties.load_properties(localization_file)

	db_pool = database.DatabasePool()
	await db_pool.setup(settings)

	async with db_pool.connection() as db_connection:
		for table in sorted(os.listdir(tables_dir)):
			fullpath = os.path.join(tables_dir, table)

			with open(fullpath) as fd:
				contents = fd.read()
				await db_connection.execute(contents)

		await db_connection.execute(
			set_language_query,
			localization)

	await db_pool.close()
	print("Success!")


def list_localizations():

	result = dict()
	for file in os.listdir(localization_dir):
		fullpath = os.path.join(localization_dir, file)

		if os.path.isfile(fullpath) and file.endswith(".ini"):
				localization, extension = file.split('.')
				loaded = properties.load_properties(fullpath)
				result[localization] = loaded['lang_name']

	return result


