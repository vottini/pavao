
import asyncio
import pavao

search_functionality = """

	SELECT id
		FROM pavao.functionality
		WHERE name = $1;

"""

insert_functionality = """

	INSERT INTO
		pavao.functionality (name)
		VALUES ($1) RETURNING id;

"""

insert_admin_access = """

	INSERT INTO
		pavao.access (functionality, cls)
		SELECT $1, cls.id FROM pavao.class cls
			WHERE cls.admin;

"""

async def assert_admin_access(db_connection, func_name):
	func_id = await db_connection.fetchrow(search_functionality, func_name)

	if func_id is None:
		async with db_connection.transaction():
			func_id = await db_connection.fetchval(insert_functionality, func_name)
			await db_connection.execute(insert_admin_access, func_id)

#-------------------------------------------------------------------------------

localized_functionalities = pavao.include('functionalities.ini')
localization = pavao.Localization(localized_functionalities)

async def localize_functionality(functionality, db_connection, parameters):
	language = await parameters.get('language')
	func_name = localization.localize(language, functionality)
	await assert_admin_access(db_connection, func_name)
	return func_name

#-------------------------------------------------------------------------------

def capitalize(text):
	if text is None: return None
	components = [comp.capitalize() for comp in text.strip().split()]
	return " ".join(components)

