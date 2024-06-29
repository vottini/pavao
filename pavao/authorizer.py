
import re
import asyncio
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone

from .loader import include
from .token import validate_token
from .i18n import LazyLocalizer

_bearer_pattern = re.compile(r"^Bearer (\S+)$")

list_roles_accesses = """

	SELECT rl.id, func.package, func.name
		FROM pavao.access acs
			INNER JOIN pavao."role" rl ON acs."role" = rl.id
			INNER JOIN pavao.functionality func ON acs.functionality = func.id;

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

list_disabled_functionalities = """

	SELECT package, "name" FROM pavao.functionality
		WHERE enabled IS FALSE;

"""

enable_query = """

	UPDATE pavao.functionality
		SET enabled = $2
		WHERE id = $1
		RETURNING package, name;

"""

retrieve_functionality = """

	SELECT package, name
		FROM pavao.functionality
		WHERE id = $1;

"""

class AuthError:
	DISABLED_ENDPOINT = 1
	MISSING_TOKEN = 2
	INVALID_TOKEN = 3
	EXPIRED_AUTH = 4
	BLOCKED_USER = 5
	NOT_ALLOWED = 6


@dataclass
class AuthData:
	account_id: str
	token: str
	expiration: int


def get_identity(entity):
	return (entity.identity()
		if isinstance(entity, LazyLocalizer)
		else entity)


class Authorizer:
	def __init__(self):
		self.roles_access = dict()
		self.functionalities = dict()
		self.packages = dict()

		self.disabled = set()
		self.users_modification = dict()
		self.blacklisted = dict()


	async def setup(self, db_conn, funcs):
		self.disabled = set(await db_conn.fetch(list_disabled_functionalities))
		accesses = await db_conn.fetch(list_roles_accesses)

		for role_id, package, functionality in accesses:
			func_set = self.roles_access.get(role_id, set())
			func_set.add((package, functionality))
			self.roles_access[role_id] = func_set

		verified_ids = [
			await db_conn.fetchval(
				assert_functionality_exists,
				get_identity(package),
				get_identity(functionality)
			)

			for package, functionality in funcs
		]

		await db_conn.execute(
			set_active_functionalities,
			verified_ids)

		self.functionalities = dict()
		for package, functionality in funcs:
			ident = (get_identity(package), get_identity(functionality))
			self.functionalities[ident] = functionality
			self.packages[ident[0]] = package

		#print(self.roles_access)
		#print(self.functionalities)

	#--------------------------------------------------------------------------

	def blacklist(self, auth_data):
		key = (auth_data.account_id, auth_data.token)
		self.blacklisted[key] = auth_data.expiration


	def mark_modified(self, user_id):
		now = int(datetime.now(timezone.utc).timestamp())
		self.users_modification[user_id] = now


	def clear_blacklist(self):
		now = int(datetime.now(timezone.utc).timestamp())
		filtered = dict()

		for key, expiration in self.blacklisted:
			if expiration < now:
				filtered[key] = expiration

		removed = len(self.blacklisted) - len(filtered)
		self.blacklisted = filtered
		return removed

	#--------------------------------------------------------------------------

	async def enable_functionality(self, db_conn, functionality_id):
		enabled = await db_conn.fetchrow(enable_query,
			functionality_id, True)

		if enabled is None:
			return False

		package, name = enabled
		self.disabled.discard((package,name))
		return True


	async def disable_functionality(self, db_conn, functionality_id):
		disabled = await db_conn.fetchrow(enable_query,
			functionality_id, False)

		if disabled is None:
			return False

		package, name = disabled
		self.disabled.add((package,name))
		return True

	#--------------------------------------------------------------------------

	async def allow_access(self, db_connection, functionality_id, role):
		func_info = await db_connection.fetchrow(
			retrieve_functionality,
			functionality_id)

		if func_info is not None:
			package, functionality = func_info
			func_set = self.roles_access.get(role, set())
			func_set.add((package, functionality))
			self.roles_access[role] = func_set


	async def remove_access(self, db_connection, functionality_id, role):
		func_info = await db_connection.fetchrow(
			retrieve_functionality,
			functionality_id)

		if func_info is not None:
			package, functionality = func_info
			func_set = self.roles_access.get(role, set())
			func_set.discard((package, functionality))

	#--------------------------------------------------------------------------

	async def validate_access(self, request, endpoint):

		complete_functionality = (
			get_identity(endpoint.package),
			get_identity(endpoint.functionality)
		)

		if complete_functionality in self.disabled:
			return False, AuthError.DISABLED_ENDPOINT

		if endpoint.public: return True, None
		authentication = request.headers.get("authorization")
		if not isinstance(authentication, str):
			return False, AuthError.MISSING_TOKEN

		found_token = _bearer_pattern.search(authentication)
		if None == found_token:
			return False, AuthError.MISSING_TOKEN

		sent_token = found_token.group(1)
		token_claims = validate_token(sent_token)
		if None == token_claims:
			return False, AuthError.INVALID_TOKEN

		subject = token_claims['sub']
		user_modification = self.users_modification.get(subject)
		if user_modification is not None and user_modification > token_claims['iat']:
			return False, AuthError.EXPIRED_AUTH

		token_id = token_claims['jti']
		if (subject, token_id) in self.blacklisted:
			return False, AuthError.BLOCKED_USER

		token_roles = token_claims['roles'].split(',')
		str_roles = filter(lambda x : len(x) > 0, token_roles)
		roles = (int(role) for role in str_roles)

		if endpoint.functionality is not None:
			for role in roles:
				accesses = self.roles_access.get(role)
				if accesses is not None and complete_functionality in accesses:
					break

			else:
				return False, AuthError.NOT_ALLOWED

		expiration = token_claims['exp']
		if expiration < int(datetime.now(timezone.utc).timestamp()):
			return False, AuthError.EXPIRED_AUTH

		return True, AuthData(subject, token_id, expiration)

	#------------------------------------------------------------

	def get_package_translation(self, package, request):
		mapping = self.packages.get(package)
		return (mapping.localize(request)
			if isinstance(mapping, LazyLocalizer)
			else mapping)


	def get_func_translation(self, package, functionality, request):
		mapping = self.functionalities.get((package, functionality))
		return (mapping.localize(request)
			if isinstance(mapping, LazyLocalizer)
			else mapping)

