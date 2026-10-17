
import re
import collections
import pavao

from pavao.persistence import StoredSettings, STORED_SETTINGS_ALLOWED_TYPES

get_setting = pavao.include("queries/get_setting.sql")
upsert_setting = pavao.include("queries/upsert_setting.sql")
list_pattern = re.compile(r"\[([^\]]+)\]")

_allowed_types = STORED_SETTINGS_ALLOWED_TYPES

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
		if isinstance(value, collections.abc.Sequence) and not isinstance(value, str):
			if len(value) == 0:
				value_type = "list"
				value = "[]"
			else:
				element_type = type(value[0])
				if element_type.__name__ not in _allowed_types:
					raise ValueError(f"Unsupported list element type for stored_settings: {element_type.__name__!r}")
				if not all(type(v) is element_type for v in value):
					raise ValueError("All elements in a stored_settings list must have the same type")
				value_type = element_type.__name__
				str_values = map(str, value)
				value = f"[{'::'.join(str_values)}]"
		else:
			value_type = type(value).__name__
			if value_type not in _allowed_types:
				raise ValueError(f"Unsupported type for stored_settings: {value_type!r}")

		async with self.internal_db.cursor() as cursor:
			await cursor.execute(upsert_setting, {
				'name': setting,
				'type': value_type,
				'value': str(value)
			})

