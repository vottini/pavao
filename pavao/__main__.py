
import os
import asyncio
import argparse
import configparser
import uvicorn
import pavao

from .config import load_settings
from .tools import setup_database

default_config = "application.yml"

cli_parser = argparse.ArgumentParser(
	prog="python -m pavao",
	description="Pavão utility tool")

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

