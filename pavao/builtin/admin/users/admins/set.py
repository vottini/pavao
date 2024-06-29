
import asyncio
import pavao

from admin.common import localizer
from admin.common import assert_admin_access

get_admin = """

	SELECT id
		FROM pavao."role"
		WHERE admin;

"""

insert_admins = """

	INSERT INTO
		pavao."assignment" (account, "role")
			SELECT id, $1 FROM pavao.account
			WHERE id = ANY($2::integer[])

		ON CONFLICT DO NOTHING;

"""

remove_admins = """

	DELETE FROM
		pavao."assignment"
			WHERE
				"role" = $1 AND
				NOT account = ANY($2::INTEGER[]);

"""


@pavao.accepts_json(string_blueprint="root integer[]")
async def process(request, response, parsed_json, db_connection, auth_data):
	parsed_json.append(auth_data.account_id)

	async with db_connection.transaction():
		admin_id = await db_connection.fetchval(get_admin)
		await db_connection.execute(insert_admins, admin_id, parsed_json)
		await db_connection.execute(remove_admins, admin_id, parsed_json)


@assert_admin_access
def pavao_endpoint():

	return {
		'method': 'PUT',
		'path': '/admin/users/admins',
		'package': localizer.map("PACKAGE"),
		'functionality': localizer.map("MODIFY_ADMIN"),
		'processor': process
	}

