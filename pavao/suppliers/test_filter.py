
import asyncio
import pavao

class TestRequestFilter(pavao.RequestFilter):
	async def init(self, loaded_settings):
		pass

	def enabled(self, endpoint_specs):
		return True

	async def allow(self, response):
		response.set_status(403)
		return False

