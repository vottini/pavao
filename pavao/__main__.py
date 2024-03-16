
import asyncio
import argparse
import uvicorn
import pavao

from .config import load_settings
from .tools import setup_database, create_admin
from .properties import load_properties

cli_parser = argparse.ArgumentParser(
	prog="python -m pavao",
	description="Pavão utility tool")

default_config = "application.yml"
cli_parser.add_argument("--config-file",
	action="store", default=default_config,
	help=f"configuration file to use. Defaults to '{default_config}'",
	metavar="FILE", required=False, type=str)

action_group = cli_parser.add_mutually_exclusive_group(required=True)

action_group.add_argument("--init-db",
	help="initializes the database using the given language",
	action="store", metavar="LANGUAGE", type=str)

action_group.add_argument("--create-admin",
	help="creates an admin account prompting the user for information",
	action="store_true")

action_group.add_argument("--import-admin",
	help="creates an admin account using the given properties FILE as specification",
	action="store", metavar="FILE", type=str)

action_group.add_argument("--execute",
	help="runs the asgi webserver serving the pavao endpoints found at DIR ",
	action="store", metavar="DIR", type=str)

args = cli_parser.parse_args()

#-------------------------------------------------------------------------------

if (localization := args.init_db) is not None:
	available_localizations = setup_database.list_localizations()

	if not localization in available_localizations:
		print(f"Error: '{localization}' is not an available localization.\n")

		print("List of installed localizations:")
		for code, localization in available_localizations.items():
			print(f"- {code} -> {localization}")

		exit(1)

	settings = load_settings(args.config_file)
	asyncio.run(setup_database.execute(settings, localization))

#-------------------------------------------------------------------------------

import readline
from getpass import getpass

def split(name):
	splitted = name.split(' ')
	not_empty = lambda x : len(x) > 0
	filtered = filter(not_empty, splitted)
	return list(filtered)


def custom_input(prompt, default_text=None):
	if default_text is not None:

		def hook():
			readline.insert_text(default_text)
			readline.redisplay()

		readline.set_pre_input_hook(hook)

	result = ""
	while 0 == len(result):
		result = input(prompt).strip()

	readline.set_pre_input_hook()
	return result


FIRST_NAME = "First name: "
OPTIONAL_LAST_NAME = "Last name (can be left blank): "
CHOOSE_LOGIN = "User login: "
TYPE_PASSWORD = "Password: "
CONFIRM_PASSWORD = "Confirm password: "
CHANGE_PASSWORD_ON_LOGIN = "Change password on next login [Y/n]? "
DEFAULT_CHANGE_PW = "n"

if args.create_admin:
	print("Creating new admin...")

	first_name = custom_input(FIRST_NAME).capitalize()
	last_name = input(OPTIONAL_LAST_NAME).strip().capitalize()
	suggested_login = ".".join(split(first_name) + split(last_name)).lower()
	login = custom_input(CHOOSE_LOGIN, suggested_login)

	password1 = getpass(TYPE_PASSWORD)
	password2 = getpass(CONFIRM_PASSWORD)

	if password1 != password2:
		print("Passwords don't match, try again:")
		password1 = getpass(TYPE_PASSWORD)
		password2 = getpass(CONFIRM_PASSWORD)

	change_pw = custom_input(
		CHANGE_PASSWORD_ON_LOGIN,
		DEFAULT_CHANGE_PW)

	if not change_pw in ['Y', 'n']:
		print("Invalid choice")

		change_pw = custom_input(
			CHANGE_PASSWORD_ON_LOGIN,
			DEFAULT_CHANGE_PW)

	specs = create_admin.AdminSpecs(first_name,
		last_name if len(last_name) > 0 else None,
		login, password1, change_pw == "Y")

	settings = load_settings(args.config_file)
	asyncio.run(create_admin.execute(settings, specs))

#-------------------------------------------------------------------------------

needed_properties = [
	"FIRST_NAME",
	"LOGIN",
	"PASSWORD",
]

def sane_name(name):
	if name is None: return None
	return name.strip().capitalize()

if (import_file := args.import_admin) is not None:
	try: admin_specs = load_properties(import_file)

	except Exception:
		print(f"Unable to read specs from file '{import_file}'")
		print("Aborting...")
		exit(1)

	for prop in needed_properties:
		if not prop.lower() in admin_specs:
			print(f"Property '{prop}' is missing")
			print("Aborting...")
			exit(1)

	specs = create_admin.AdminSpecs(
		sane_name(admin_specs["first_name"]),
		sane_name(admin_specs.get("last_name")),
		admin_specs["login"].lower(),
		admin_specs["password"],
		admin_specs.get("change_password") == "YES"
	)

	settings = load_settings(args.config_file)
	asyncio.run(create_admin.execute(settings, specs))

#-------------------------------------------------------------------------------

if (endpoints_dir := args.execute) is not None:
	handler = pavao.Handler(
		args.config_file,
		args.execute
	)

	asgi_config = uvicorn.Config(
		app=handler.get_app(),
		loop=handler.loop)

	asgi_server = uvicorn.Server(asgi_config)
	handler.loop.run_until_complete(asgi_server.serve())

