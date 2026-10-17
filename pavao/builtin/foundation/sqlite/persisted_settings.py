
import re
import collections
import pavao

from pavao.persistence import StoredSettings

get_setting = pavao.include("queries/get_setting.sql")
upsert_setting = pavao.include("queries/upsert_setting.sql")
list_pattern = re.compile(r"\[([^\]]+)\]")

_allowed_types = {
	'int': int,
	'float': float,
	'str': str,
	'bool': bool,
}

class PersistedSettings(StoredSettings):
	def __init__(self, internal_db):
		self.internal_db = internal_db


	async def get(self, setting):
		async with self.internal_db.execute(get_setting, [setting]) as cursor:
			row = await cursor.fetchone()
			if row is None:
				return None

		typ, value = row
		if value == "[]":
			return []

		ctor = _allowed_types.get(typ)
		if ctor is None:
			raise ValueError(f"Unsupported type in stored_settings: {typ!r}")

		list_search = list_pattern.search(value)
		if list_search is not None:
			list_content = list_search.group(1)
			return [ ctor(vle) for vle in list_content.split("::") ]

		return ctor(value)


	async def set(self, setting, value):
		value_type = type(value).__name__
		original_value = value

		if isinstance(value, collections.abc.Sequence) and not isinstance(value, str):
			if len(value) == 0:
				value_type = "list"
				value = "[]"
			else:
				value_type = type(value[0]).__name__
				str_values = map(str, value)
				value = f"[{'::'.join(str_values)}]"

		async with self.internal_db.cursor() as cursor:
			await cursor.execute(upsert_setting, {
				'name': setting,
				'type': value_type,
				'value': str(value)
			})

