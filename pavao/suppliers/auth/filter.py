
import asyncio
import pavao

class AuthFilter(pavao.RequestFilter):
	async def init(self, loaded_settings):
		pass


	def enabled(self, endpoint_specs):
		return True


	async def allow(self, request, response, authorizer):
		print(authorizer)
		return True

