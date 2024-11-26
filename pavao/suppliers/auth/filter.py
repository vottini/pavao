
import asyncio
import pavao

pavao.import_module('authorizer')
pavao.import_module('common')


class AuthFilter(pavao.RequestFilter):
	async def init(self, loaded_settings):
		common.process_config(loaded_settings)


	async def enabled(self, endpoint_specs, db_connection):
		if not common.enabled:
			return False

		if endpoint_specs.get('public') is True: return False
		await authorizer.instance.register_functionality(
			endpoint_specs, db_connection)

		return True


	async def allow(self, access_validation, response):
		print("ALLOW", access_validation)
		has_access, validation_outcome = access_validation
		if has_access: return True

		if validation_outcome in (
			authorizer.AuthError.MISSING_TOKEN,
			authorizer.AuthError.INVALID_TOKEN,
			authorizer.AuthError.EXPIRED_AUTH,
			authorizer.AuthError.BLOCKED_USER
		): status = 401

		if validation_outcome is authorizer.AuthError.NOT_ALLOWED: status = 403
		if validation_outcome is authorizer.AuthError.DISABLED_ENDPOINT: status = 410
		response.set_status(status)
		return False
