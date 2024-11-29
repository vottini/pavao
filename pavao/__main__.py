
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
	help=f"configuration file to use. Defaults to '{default_config}'",
	action="store", metavar="FILE", required=False, type=str,
	default=default_config)

cli_parser.add_argument("--foundation",
	help=f"directory to load suppliers and filters from",
	action="store", metavar="DIR", required=False, type=str,
	default=None)

action_group = cli_parser.add_mutually_exclusive_group(required=True)

#action_group.add_argument("--create-admin",
#	help="creates an admin account prompting the user for information",
#	action="store_true")
#
#action_group.add_argument("--import-admin",
#	help="creates an admin account using the given properties FILE as specification",
#	action="store", metavar="FILE", type=str)

action_group.add_argument("--execute",
	help="runs the asgi webserver serving the pavao endpoints found at DIR ",
	action="store", metavar="DIR", type=str)

args = cli_parser.parse_args()

#-------------------------------------------------------------------------------

#import readline
#from getpass import getpass
#
#def split(name):
#	splitted = name.split(' ')
#	not_empty = lambda x : len(x) > 0
#	filtered = filter(not_empty, splitted)
#	return list(filtered)
#
#
#def custom_input(prompt, default_text=None):
#	if default_text is not None:
#
#		def hook():
#			readline.insert_text(default_text)
#			readline.redisplay()
#
#		readline.set_pre_input_hook(hook)
#
#	result = ""
#	while 0 == len(result):
#		result = input(prompt).strip()
#
#	readline.set_pre_input_hook()
#	return result
#
#
#FIRST_NAME = "First name: "
#OPTIONAL_LAST_NAME = "Last name (can be left blank): "
#CHOOSE_LOGIN = "User login: "
#TYPE_PASSWORD = "Password: "
#CONFIRM_PASSWORD = "Confirm password: "
#CHANGE_PASSWORD_ON_LOGIN = "Change password on next login [Y/n]? "
#DEFAULT_CHANGE_PW = "n"
#
#if args.create_admin:
#	print("Creating new admin...")
#
#	first_name = custom_input(FIRST_NAME).capitalize()
#	last_name = input(OPTIONAL_LAST_NAME).strip().capitalize()
#	suggested_login = ".".join(split(first_name) + split(last_name)).lower()
#	login = custom_input(CHOOSE_LOGIN, suggested_login)
#
#	password1 = getpass(TYPE_PASSWORD)
#	password2 = getpass(CONFIRM_PASSWORD)
#
#	while password1 != password2:
#		print("Passwords don't match, try again:")
#		password1 = getpass(TYPE_PASSWORD)
#		password2 = getpass(CONFIRM_PASSWORD)
#
#	change_pw = custom_input(
#		CHANGE_PASSWORD_ON_LOGIN,
#		DEFAULT_CHANGE_PW)
#
#	while not change_pw in ['Y', 'n']:
#		print("Invalid choice")
#
#		change_pw = custom_input(
#			CHANGE_PASSWORD_ON_LOGIN,
#			DEFAULT_CHANGE_PW)
#
#	specs = create_admin.AdminSpecs(first_name,
#		last_name if len(last_name) > 0 else None,
#		login, password1, change_pw == "Y")
#
#	settings = load_settings(args.config_file)
#	asyncio.run(create_admin.execute(settings, specs))
#
##-------------------------------------------------------------------------------
#
#needed_properties = [
#	"FIRST_NAME",
#	"LOGIN",
#	"PASSWORD",
#]
#
#def sane_name(name):
#	if name is None: return None
#	return name.strip().capitalize()
#
#if (import_file := args.import_admin) is not None:
#	try: admin_specs = load_properties(import_file)
#
#	except Exception:
#		print(f"Unable to read specs from file '{import_file}'")
#		print("Aborting...")
#		exit(1)
#
#	for prop in needed_properties:
#		if not prop.lower() in admin_specs:
#			print(f"Property '{prop}' is missing")
#			print("Aborting...")
#			exit(1)
#
#	specs = create_admin.AdminSpecs(
#		sane_name(admin_specs["first_name"]),
#		sane_name(admin_specs.get("last_name")),
#		admin_specs["login"].lower(),
#		admin_specs["password"],
#		admin_specs.get("change_password") == "YES"
#	)
#
#	settings = load_settings(args.config_file)
#	asyncio.run(create_admin.execute(settings, specs))

#-------------------------------------------------------------------------------

if (modules_dir := args.execute) is not None:
	is_default_config = args.config_file == default_config
	foundation_dir = args.foundation

	server = pavao.Server(
		args.config_file, is_default_config,
		foundation_dir, modules_dir)

	# monkey patch sigterm handler in uvicorn
	# https://stackoverflow.com/a/59887076

	original_handler = uvicorn.Server.handle_exit

	def handle_exit(*args, **kwargs):
		server.deactivate()
		original_handler(*args, **kwargs)

	uvicorn.Server.handle_exit = handle_exit

	asgi_config = uvicorn.Config(
		host="0.0.0.0",
		app=server.get_app(),
		loop=server.loop)

	asgi_server = uvicorn.Server(asgi_config)
	try: server.loop.run_until_complete(asgi_server.serve())
	except KeyboardInterrupt:
		pass

