
import asyncio
import pavao

pavao.import_module('token')
pavao.import_module('authorizer')
pavao.import_module('common')

#-------------------------------------------------------------------------------

async def validate_access(request, endpoint_specs, authorizer):
	return await authorizer.validate_access(request,
		endpoint_specs)


async def select_data(access_validation):
	has_access, validation_outcome = access_validation
	return validation_outcome if has_access else None


async def retrieve_authorizer():
	return authorizer.instance

#-------------------------------------------------------------------------------

class AuthSupplier(pavao.ParameterSupplier):
	def configure(self, loaded_settings):
		common.process_config(loaded_settings)


	async def initialize(self, db_connection):
		if not common.enabled: return
		await authorizer.instance.setup(
			db_connection)


	def parameters_supplied(self):
		if not common.enabled:
			return dict()

		return {
			'access_validation': [
				validate_access,
				None
			],

			'auth_data': [
				select_data,
				None
			],

			'authorizer': [
				retrieve_authorizer,
				None
			]
		}

