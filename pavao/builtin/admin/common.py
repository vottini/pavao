
import os
import functools
import pavao

localization_dir = pavao.path_to("localization")

#------------------------------------------------------------------------------

functionalities_path = os.path.join(localization_dir, 'functionalities')
localizer = pavao.ModuleLocalizer("ADMIN", functionalities_path)
package_mapper = localizer.map("PACKAGE")


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
		SELECT $1, rl.id FROM pavao."role" rl WHERE rl.admin
		ON CONFLICT DO NOTHING;

"""

def assert_admin_access(fnc):

	@functools.wraps(fnc)
	async def wrapped(loaded_settings, persisted_settings, db_connection):

		all_args = {
			'loaded_settings': loaded_settings,
			'persisted_settings': persisted_settings,
			'db_connection': db_connection,
		}

		adapted_fnc = pavao.adapter(fnc)
		result = await adapted_fnc(all_args)
		if not isinstance(result, dict):
			return result

		package_mapper = result.get("package")
		func_mapper = result.get("functionality")
		if None in (package_mapper, func_mapper):
			return result

		func_id = await db_connection.fetchval(search_functionality,
			package_mapper.identity(),
			func_mapper.identity())

		if func_id is None:
			async with db_connection.transaction():
				func_id = await db_connection.fetchval(insert_functionality,
					package_mapper.identity(),
					func_mapper.identity())

		await db_connection.execute(
			insert_admin_access,
			func_id)

		return result

	return wrapped

#------------------------------------------------------------------------------

messages_path = os.path.join(localization_dir, 'messages')
messages_i18n = pavao.Internationalization(messages_path)

def create_message_localizer(request):
	accepted_languages = request.parse_locale_priority()
	return messages_i18n.create_localizer(accepted_languages)

#------------------------------------------------------------------------------

def capitalize(text):
	if text is None: return None
	components = [comp.capitalize() for comp in text.strip().split()]
	return " ".join(components)

