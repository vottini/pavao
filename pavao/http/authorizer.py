
import re
import asyncio
import time

from ..utils import include
from .token import validateToken

_bearer_pattern = re.compile(r"^Bearer (\S+)$")

list_classes = """

	SELECT
		cls.id AS class_id,
		func.name AS func_name

		FROM pavao.access acs
			INNER JOIN pavao.class cls ON acs.cls = cls.id 
			INNER JOIN pavao.functionality func ON acs.functionality = func.id;

"""

class AuthData:
	def __init__(self, login, token, expiration):
		self.login = login
		self.token = token
		self.expiration = expiration


class Authorizer:
	def __init__(self):
		self.class_access = dict()
		self.users_modification = dict()
		self.blacklisted = dict()


	async def setup(self, db_conn):
		accesses = await db_conn.fetch(list_classes)

		for class_id, functionality in accesses:
			func_set = self.class_access.get(class_id, set())
			func_set.add(functionality)
			self.class_access[class_id] = func_set


	def blacklist(self, auth_data):
		key = (auth_data.login, auth_data.token)
		self.blacklisted[key] = auth_data.expiration


	async def validate_access(self, request, endpoint):
		if not endpoint.public:
			authentication = request.headers.get("authorization")
			if None == authentication:
				return False, None

			found_token = _bearer_pattern.search(authentication)
			if None == found_token:
				return False, None

			sentToken = found_token.group(1)
			tokenClaims = validateToken(sentToken)
			if None == tokenClaims:
				return False, None

			subject = tokenClaims['sub']
			user_modification = self.users_modification.get(subject)
			if user_modification is not None and user_modification > tokenClaims['iat']:
				return False, None

			token_id = tokenClaims['jti']
			if (subject, token_id) in self.blacklisted:
				return False, None			

			subject_classes = [ int(cls) for cls in tokenClaims['cls'].split(',') ]

			if endpoint.functionality is not None:
				for cls in subject_classes:
					accesses = self.class_access.get(cls)
					if accesses is not None and endpoint.functionality in accesses:
						break

				else:
					return False, None

			expiration = tokenClaims['exp']
			return True, AuthData(subject, token_id, expiration)
		
		return True, None

