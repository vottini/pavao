
import asyncio
import argparse
import uvicorn
import pavao

from .config import load_settings

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

action_group.add_argument("--execute",
	help="runs the asgi webserver serving the pavao endpoints found at DIR ",
	action="store", metavar="DIR", type=str)

args = cli_parser.parse_args()

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

