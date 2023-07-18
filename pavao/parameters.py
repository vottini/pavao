
import asyncio
import builtins
import collections
import re

list_pattern = re.compile(r"\[([^\]]+)\]")
get_query = "SELECT type, value FROM pavao.parameters WHERE name = $1"

upsert_query = """

INSERT INTO
	pavao.parameters (name, type, value) 
	VALUES ($1, $2, $3)

	ON CONFLICT (name) DO UPDATE 
		SET type = excluded.type, 
			value = excluded.value;

"""

class Parameters:
	def __init__(self, db_pool):
		self.listeners = dict()
		self.db_pool = db_pool


	async def get(self, name):
		async with self.db_pool.connection() as db_connection:
			row = await db_connection.fetchrow(get_query, name)
			if row is None: return None

			typ, value = row
			list_search = list_pattern.search(value)
			ctor = getattr(builtins, typ)

			if list_search is not None:
				list_content = list_search.group(1)
				return [ ctor(vle) for vle in list_content.split("::") ]

			return ctor(value)
			
	
	def monitor(self, name, callback):
		key_listeners = self.listeners.get(name, list())
		key_listeners.append(callback)
		self.listeners[name] = key_listeners


	async def set(self, name, value):
		original_value = value

		typ = type(original_value).__name__
		if isinstance(value, collections.abc.Sequence) and not isinstance(value, str):
			typ = type(value[0]).__name__
			str_values = map(str, value)
			value = f"[{'::'.join(str_values)}]"

		async with self.db_pool.connection() as db_connection:
			await db_connection.execute(upsert_query, name, typ, str(value))

		listeners = self.listeners.get(name, list())
		for listener in listeners:
			listener(original_value)

#------------------------------------------------------------------------------

__all__ = [
	"Parameters"
]

