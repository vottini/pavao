
import asyncio
import pavao

select_user = pavao.include('queries/select_user.sql')
count_admin_roles = pavao.include('queries/count_admin_roles.sql')
blueprints = pavao.path_to('blueprints.jbp')

@pavao.generates_json(file_blueprint=blueprints, with_root="userInfo")
async def process(authorizer, request, db_connection, auth_data):
	user_id = auth_data.account_id

	user_info = await db_connection.fetchrow(select_user, user_id)
	admin_roles = await db_connection.fetchval(count_admin_roles, user_id)
	token_accesses = authorizer.list_accesses(request)

	accesses = [
		{ 'package': pkg, 'functionality': func }
		for pkg, func in token_accesses
	]

	return pavao.assemble_dicts(user_info,
		administrator=admin_roles > 0,
		accesses=accesses,
		id=user_id)


def pavao_endpoint():

	return {
		'method': 'GET',
		'path': '/self',
		'processor': process
	}

