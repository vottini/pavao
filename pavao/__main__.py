
import asyncio
import argparse
import uvicorn
import pavao

from .config import load_settings

def main():
	config_detail = "If 'config_file' doesn't exist, pavao will still try to run using default values"

	cli_parser = argparse.ArgumentParser(
		prog="python -m pavao",
		description="Pavão execution interface",
		epilog=config_detail)

	default_config = "application.yml"
	cli_parser.add_argument("--config-file",
		help=f"configuration file to use. Defaults to '{default_config}'",
		action="store", metavar="FILE", required=False, type=str,
		default=default_config)

	default_port = 8000
	cli_parser.add_argument("--port",
		help=f"port where the service will answer requests. Defaults to {default_port}",
		action="store", metavar="PORT", required=False, type=int,
		default=default_port)

	cli_parser.add_argument("--foundation",
		help=f"directory to load suppliers and filters from",
		action="store", metavar="DIR", required=False, type=str,
		default=None)

	cli_parser.add_argument("modules",
		help=f"directory of modules to load",
		action="store", metavar="MODULES_DIR", type=str)

	args = cli_parser.parse_args()

	#-------------------------------------------------------------------------------

	is_default_config = args.config_file == default_config
	foundation_dir = args.foundation

	server = pavao.Server(
		args.config_file,
		is_default_config,
		foundation_dir,
		args.modules)

	# monkey patch sigterm handler in uvicorn
	# https://stackoverflow.com/a/59887076

	original_handler = uvicorn.Server.handle_exit

	def handle_exit(*args, **kwargs):
		server.deactivate()
		original_handler(*args, **kwargs)

	uvicorn.Server.handle_exit = handle_exit

	asgi_config = uvicorn.Config(
		host="0.0.0.0",
		port=args.port,
		app=server.get_app())

	asgi_server = uvicorn.Server(asgi_config)
	try: server.loop.run_until_complete(asgi_server.serve())
	except KeyboardInterrupt:
		pass


if __name__ == "__main__":
	main()
