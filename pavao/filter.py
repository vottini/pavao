
class RequestFilter:
	def enabled(self, endpoint): return False
	def allow(self, *params): return True

