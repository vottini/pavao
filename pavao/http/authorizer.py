
import re
import asyncio
import time

from ..utils import include
from .token import validate_token

_bearer_pattern = re.compile(r"^Bearer (\S+)$")

list_roles_accesses = """

	SELECT rl.id, func.name
		FROM pavao.access acs
			INNER JOIN pavao."role" rl ON acs."role" = rl.id
			INNER JOIN pavao.functionality func ON acs.functionality = func.id

		WHERE func.enabled;

"""

list_functionality_roles = """

	SELECT rl.id
		FROM pavao.access acs
			INNER JOIN pavao."role" rl ON acs."role" = rl.id
			INNER JOIN pavao.functionality func ON acs.functionality = func.id

		WHERE func.name = $1;

"""

assert_functionality_exists = """

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
							fnc.package = $1 AND
							fnc."name" = $2
				)

		RETURNING id, enabled
	)

	SELECT id FROM existing UNION ALL
	SELECT id FROM created;

"""

set_active_functionalities = """

	UPDATE pavao.functionality
		SET active = (id = ANY($1::INTEGER[]));

"""


class AuthData:
	def __init__(self, account_id, token, expiration):
		self.account_id = account_id
		self.token = token
		self.expiration = expiration


class Authorizer:
	def __init__(self):
		self.roles_access = dict()
		self.users_modification = dict()
		self.blacklisted = dict()


	async def setup(self, db_conn, funcs):
		accesses = await db_conn.fetch(
			list_roles_accesses)

		for role_id, functionality in accesses:
			func_set = self.roles_access.get(role_id, set())
			func_set.add(functionality)
			self.roles_access[role_id] = func_set

		verified_ids = list()
		for package, functionality in funcs:
			verified_ids.append(await db_conn.fetchval(
					assert_functionality_exists,
					package, functionality))

		await db_conn.execute(
			set_active_functionalities,
			verified_ids)


	def blacklist(self, auth_data):
		key = (auth_data.account_id, auth_data.token)
		self.blacklisted[key] = auth_data.expiration


	async def enable_functionality(self, db_conn, functionality):
		roles_with_func = await db_conn.fetch(
			list_functionality_roles,
			functionality)

		for role_id in roles_with_func:
			func_set = self.roles_access.get(role_id, set())
			func_set.add(functionality)
			self.roles_access[role_id] = func_set


	def disable_functionality(self, functionality):
		for func_set in self.roles_access.values():
			func_set.discard(functionality)


	async def validate_access(self, request, endpoint):
		if endpoint.public: return True, None
		authentication = request.headers.get("authorization")
		if not isinstance(authentication, str):
			return False, None

		found_token = _bearer_pattern.search(authentication)
		if None == found_token:
			return False, None

		sent_token = found_token.group(1)
		token_claims = validate_token(sent_token)
		if None == token_claims:
			return False, None

		subject = token_claims['sub']
		user_modification = self.users_modification.get(subject)
		if user_modification is not None and user_modification > token_claims['iat']:
			return False, None

		token_id = token_claims['jti']
		if (subject, token_id) in self.blacklisted:
			return False, None

		roles = list(filter(
			lambda x : len(x) > 0,
			token_claims['roles'].split(',')))

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

		expiration = token_claims['exp']
		return True, AuthData(subject, token_id, expiration)

