
import re
import asyncio
import pavao

from datetime import datetime
from datetime import timezone
from dataclasses import dataclass
from pavao import LazyLocalizer

list_roles_accesses = pavao.include("./queries/list_roles_accesses.sql")
list_functionality_roles = pavao.include("./queries/list_functionality_roles.sql")
assert_functionality_exists = pavao.include("./queries/assert_functionality_exists.sql")
set_active_functionalities = pavao.include("./queries/set_active_functionalities.sql")
list_disabled_functionalities = pavao.include("./queries/list_disabled_functionalities.sql")
enable_functionality = pavao.include("./queries/enable_functionality.sql")
retrieve_functionality = pavao.include("./queries/retrieve_functionality.sql")

pavao.import_module('token')
_bearer_pattern = re.compile(r"^Bearer (\S+)$")

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

#-------------------------------------------------------------------------------

def get_identity(entity):
	return (entity.identity()
		if isinstance(entity, LazyLocalizer)
		else entity)


def parse_roles(token_claims):
	token_roles = token_claims['roles'].split(',')
	str_roles = filter(lambda x : len(x) > 0, token_roles)
	return (int(role) for role in str_roles)

#-------------------------------------------------------------------------------

class Authorizer:
	def __init__(self):
		self.roles_access = dict()
		self.functionalities = dict()
		self.packages = dict()

		self.disabled = set()
		self.users_modification = dict()
		self.blacklisted = dict()


	async def setup(self, db_connection):
		self.disabled = set(await db_connection.fetch(list_disabled_functionalities))
		accesses = await db_connection.fetch(list_roles_accesses)

		for role_id, package, functionality in accesses:
			func_set = self.roles_access.get(role_id, set())
			func_set.add((package, functionality))
			self.roles_access[role_id] = func_set

	#--------------------------------------------------------------------------

	async def register_functionality(self, endpoint_specs, db_connection):
		functionality = endpoint_specs.get("functionality")
		if functionality is None:
			return

		package = endpoint_specs.get("package")
		await db_connection.fetchval(assert_functionality_exists,
			get_identity(package), get_identity(functionality))

		#await db_connection.execute(
		#	set_active_functionalities,
		#	verified_ids)

		ident = (
			get_identity(package),
			get_identity(functionality)
		)

		self.functionalities[ident] = functionality
		self.packages[ident[0]] = package


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
		enabled = await db_conn.fetchrow(enable_functionality,
			functionality_id, True)

		if enabled is None:
			return False

		package, name = enabled
		self.disabled.discard((package,name))
		return True


	async def disable_functionality(self, db_conn, functionality_id):
		disabled = await db_conn.fetchrow(enable_functionality,
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

	def grep_token_claims(self, request):
		authorization = request.headers.get("authorization")
		if not isinstance(authorization, str):
			return False, AuthError.MISSING_TOKEN

		found_token = _bearer_pattern.search(authorization)
		if found_token is None:
			return False, AuthError.MISSING_TOKEN

		sent_token = found_token.group(1)
		if (token_claims := token.validate_token(sent_token)) is not None:
			return True, token_claims

		return False, AuthError.INVALID_TOKEN


	async def validate_access(self, request, endpoint_specs):
		functionality = endpoint_specs.get('functionality')

		complete_functionality = (
			get_identity(endpoint_specs.get('package')),
			get_identity(functionality)
		)

		if complete_functionality in self.disabled:
			return False, AuthError.DISABLED_ENDPOINT

		validated, outcome = self.grep_token_claims(request)
		if not validated: return False, outcome

		token_claims = outcome
		subject = token_claims['sub']
		user_modification = self.users_modification.get(subject)
		if user_modification is not None and user_modification > token_claims['iat']:
			return False, AuthError.EXPIRED_AUTH

		token_id = token_claims['jti']
		if (subject, token_id) in self.blacklisted:
			return False, AuthError.BLOCKED_USER

		if functionality is not None:
			for role in parse_roles(token_claims):
				accesses = self.roles_access.get(role)
				if accesses is not None and complete_functionality in accesses:
					break

			else:
				return False, AuthError.NOT_ALLOWED

		expiration = token_claims['exp']
		if expiration < int(datetime.now(timezone.utc).timestamp()):
			return False, AuthError.EXPIRED_AUTH

		return True, AuthData(subject, token_id, expiration)


	def list_accesses(self, request):
		validated, outcome = self.grep_token_claims(request)
		result = set()

		if validated:
			token_claims = outcome
			for role in parse_roles(token_claims):
				accesses = self.roles_access.get(role)
				if accesses is not None:
					result.update(accesses)

		return tuple(result)

	#------------------------------------------------------------

	def get_package_translation(self, package, request):
		accepted_languages = request.parse_locale_priority()
		mapping = self.packages.get(package)

		return (mapping.localize(accepted_languages)
			if isinstance(mapping, LazyLocalizer)
			else mapping)


	def get_func_translation(self, package, functionality, request):
		accepted_languages = request.parse_locale_priority()
		mapping = self.functionalities.get(
			(package, functionality))

		return (mapping.localize(accepted_languages)
			if isinstance(mapping, LazyLocalizer)
			else mapping)

#------------------------------------------------------------

instance = Authorizer()

