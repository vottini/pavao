
import re
import asyncio
import time

from ..utils import include
from .token import validateToken

_bearer_pattern = re.compile(r"^Bearer (\S+)$")

list_roles_accesses = """

	SELECT
		rl.id AS role_id,
		func.name AS func_name

		FROM pavao.access acs
			INNER JOIN pavao."role" rl ON acs."role" = rl.id 
			INNER JOIN pavao.functionality func ON acs.functionality = func.id

		WHERE func.enabled;

"""

create_or_retrieve_functionality = """

	WITH
	
	existing AS (
		SELECT id, enabled
			FROM pavao.functionality func

			WHERE
				func.package = $1 AND
				func."name" = $2
	),
	
	created AS (
		INSERT INTO pavao.functionality (package, name)
			SELECT $1, $2
				WHERE NOT EXISTS (
					SELECT 1
						FROM pavao.functionality fnc

						WHERE
							fnc.package = $1
							fnc."name" = $2
				)
	
		RETURNING id, enabled
	)
	
	SELECT * FROM existing UNION ALL
	SELECT * FROM created;

"""


class AuthData:
	def __init__(self, login, token, expiration):
		self.login = login
		self.token = token
		self.expiration = expiration


class Authorizer:
	def __init__(self):
		self.roles_access = dict()
		self.users_modification = dict()
		self.blacklisted = dict()


	async def setup(self, db_conn):
		accesses = await db_conn.fetch(
			list_roles_accesses)

		for role_id, functionality in accesses:
			func_set = self.roles_access.get(role_id, set())
			func_set.add(functionality)
			self.roles_access[role_id] = func_set


	def blacklist(self, auth_data):
		key = (auth_data.login, auth_data.token)
		self.blacklisted[key] = auth_data.expiration


	def enable_functionality(self, functionality, value):
		# TODO
		pass


	async def validate_access(self, request, endpoint):
		if endpoint.public: return True, None
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

		roles = list(filter(
			lambda x : len(x) > 0,
			tokenClaims['roles'].split(',')))

		subject_roles = ([ int(role) for role in roles ]
			if len(roles) > 0
			else list())

		if endpoint.functionality is not None:
			for role in subject_roles:
				accesses = self.roles_access.get(role)
				if accesses is not None and endpoint.functionality in accesses:
					break

			else:
				return False, None

		expiration = tokenClaims['exp']
		return True, AuthData(subject, token_id, expiration)

