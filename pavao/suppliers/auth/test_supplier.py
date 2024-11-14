
import asyncio
import pavao

auth_schema = {
	"enabled": False
}

pavao.import_module('token')
pavao.import_module('authorizer')

#-------------------------------------------------------------------------------

async def validate_request(request):
	return None

async def retrieve_authorizer():
	return authorizer.instance

#-------------------------------------------------------------------------------

class AuthSupplier(pavao.ParameterSupplier):
	def __init__(self):
		self.enabled = False


	def configure(self, loaded_settings):
		auth_settings = loaded_settings.get_setting("pavao.auth", auth_schema)
		if auth_settings is not None and auth_settings['enabled']:
			pavao.Logger.info("Builtin auth system enabled")


	async def initialize(self, db_connection):
		if not self.enabled:
			return


	def parameters_supplied(self):

		return {
			'access_validation': [
				validate_request,
				None
			],

			'auth_data': [
				validate_request,
				None
			],

			'authorizer': [
				retrieve_authorizer,
				None
			],
		}

