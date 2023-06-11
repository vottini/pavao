
import re
import asyncio

_bearer_pattern = re.compile(r"Bearer (\w+)")

class Authorizer:
	async def validate_access(self, request, endpoint, db_conn):
		if not endpoint.public:
			authentication = request.headers.get("authorization")
			if None == authentication:
				return False

			found_token = _bearer_pattern.search(authentication)
			if None == found_token:
				return False

			sentToken = found_token.group(1)
			print(f"TOKEN = {sentToken}")
		
		return True

