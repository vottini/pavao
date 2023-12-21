
import asyncio
import pavao

select_user = pavao.include('queries/select_user.sql')
count_admin_roles = pavao.include('queries/count_admin_roles.sql')
blueprints = pavao.path_to('blueprints.jbp')

@pavao.generates_json(file_blueprint=blueprints, with_root="userInfo")
async def process(db_connection, auth_data):
	user_info = await db_connection.fetchrow(select_user, auth_data.account_id)
	admin_roles = await db_connection.fetchval(count_admin_roles, auth_data.account_id)
	return pavao.assemble_dicts(user_info, administrator=admin_roles > 0)


def pavao_endpoint():
	return {
		'method': 'GET',
		'path': '/self',
		'processor': process
	}

