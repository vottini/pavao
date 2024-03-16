
import os
import asyncio
from dataclasses import dataclass
from argon2 import PasswordHasher

from .. import database
from .. import properties
from .. import loader

script_path = os.path.dirname(os.path.realpath(__file__))
localization_dir = os.path.join(script_path, "localization")

@dataclass
class AdminSpecs:
	first_name: str
	last_name: str
	login: str
	password: str
	change_pw: bool


get_login_count = loader.include("queries/get_login_count.sql")
get_localization = loader.include("queries/get_localization.sql")
insert_user = loader.include("queries/insert_user.sql")
insert_authentication = loader.include("queries/insert_authentication.sql")
create_admin_role = loader.include("queries/create_admin_role.sql")
assign_admin = loader.include("queries/assign_admin.sql")


async def execute(settings, admin_specs):
	db_pool = database.DatabasePool()
	await db_pool.setup(settings)

	try:
		async with db_pool.connection() as db_connection:
			login_count = await db_connection.fetchval(
				get_login_count, admin_specs.login)

			if login_count > 0:
				print(f"Login '{admin_specs.login}' already exists, aborting...")
				return

			localization = await db_connection.fetchval(get_localization)
			if localization is None: raise Exception("Localization not defined")

	except Exception as e:
		print("Unable to find database localization.")
		print("Has the database been initialized?")
		return

	localization_file = os.path.join(localization_dir, f"{localization}.ini")
	localization_specs = properties.load_properties(localization_file)

	async with db_pool.connection() as db_connection:
		account = await db_connection.fetchval(insert_user, admin_specs.login,
			admin_specs.first_name,
			admin_specs.last_name)

		passwordHash = PasswordHasher().hash(admin_specs.password)
		await db_connection.execute(insert_authentication,
			account, passwordHash, admin_specs.change_pw)

		role = await db_connection.fetchval(create_admin_role,
			localization_specs["administrator_group"])

		await db_connection.execute(assign_admin, account, role)
		print("Success!")

	await db_pool.close()

