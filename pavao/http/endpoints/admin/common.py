
import os
import asyncio
import pavao

search_functionality = """

	SELECT id
		FROM pavao.functionality
		WHERE
			package = $1 AND
			name = $2;

"""

insert_functionality = """

	INSERT INTO
		pavao.functionality (package, name)
		VALUES ($1, $2) RETURNING id;

"""

insert_admin_access = """

	INSERT INTO
		pavao.access (functionality, "role")
		SELECT $1, rl.id FROM pavao."role" rl
			WHERE rl.admin;

"""

async def assert_admin_access(db_connection, package_name, func_name):
	func_id = await db_connection.fetchrow(search_functionality,
		package_name, func_name)

	if func_id is None:
		async with db_connection.transaction():
			func_id = await db_connection.fetchval(insert_functionality,
				package_name, func_name)

			await db_connection.execute(insert_admin_access, func_id)

#-------------------------------------------------------------------------------

_functionalities_path = os.path.join('localization', 'functionalities')
_functionalities_i18n = pavao.Internationalization(
	pavao.path_to(_functionalities_path)
)

async def localize_functionality(functionality, db_connection, persisted_settings):
	language = await persisted_settings.get('language')
	package_name = _functionalities_i18n.localize(language, "PACKAGE")
	func_name = _functionalities_i18n.localize(language, functionality)
	await assert_admin_access(db_connection, package_name, func_name)
	return package_name, func_name

#-------------------------------------------------------------------------------

_messages_path = os.path.join('localization', 'messages')
_messages_i18n = pavao.Internationalization(
	pavao.path_to(_messages_path)
)

def create_message_localizer(request):
	return _messages_i18n.create_localizer(request)

#-------------------------------------------------------------------------------

def capitalize(text):
	if text is None: return None
	components = [comp.capitalize() for comp in text.strip().split()]
	return " ".join(components)


