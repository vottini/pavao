
import re
import asyncio
import builtins
import collections
import pavao

list_pattern = re.compile(r"\[([^\]]+)\]")

get_query = """

  SELECT type, value
    FROM settings
    WHERE name = $1;

"""

upsert_query = """

  INSERT INTO
    settings (name, type, value)
    VALUES ($1, $2, $3)

    ON CONFLICT (name) DO UPDATE
      SET type = excluded.type,
          value = excluded.value;

"""


class PersistedSettings:
	def __init__(self, sqlite_cursor):
		self.sqlite_cursor = sqlite_cursor


	async def get(self, name):
		row = await self.sqlite_cursor.fetchrow(get_query, name)
		if row is None:
			return None

		typ, value = row
		list_search = list_pattern.search(value)
		ctor = getattr(builtins, typ)

		if list_search is not None:
			list_content = list_search.group(1)
			return [ ctor(vle) for vle in list_content.split("::") ]

		return ctor(value)


	async def set(self, name, value):
		value_type = type(value).__name__
		original_value = value

		if isinstance(value, collections.abc.Sequence) and not isinstance(value, str):
			value_type = type(value[0]).__name__
			str_values = map(str, value)
			value = f"[{'::'.join(str_values)}]"

		await self.sqlite_cursor.execute(upsert_query,
			name, value_type, str(value))

#-------------------------------------------------------------------------------

class StoredSettingsSupplier(pavao.ParameterSupplier):
	async def create_stored_settings(self, sqlite_cursor):
		return PersistedSettings(sqlite_cursor)

	def parameters_supplied(self):
		return {
			'stored_settings': [
				self.create_stored_settings,
				None
			],
		}

