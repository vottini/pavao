
import asyncio
import pavao

from admin.common import localizer
from admin.common import create_message_localizer
from admin.common import assert_admin_access

async def process(request, response, db_connection, path_variables, server):
	authorizer = server.authorizer
	success = await authorizer.enable_functionality(db_connection,
		path_variables['functionality'])

	if not success:
		response.set_status(404)
		message_localizer = create_message_localizer(request)
		message_localizer.assign_response_error(response,
			"FUNCTIONALITY_NOT_FOUND")


@assert_admin_access
def pavao_endpoint():

	return {
		'method': 'PUT',
		'path': '/admin/functionalities/{functionality:int}/enable',
		'package': localizer.map("PACKAGE"),
		'functionality': localizer.map("MANAGE_FUNCTIONALITIES"),
		'processor': process
	}

