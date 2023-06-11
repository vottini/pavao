
import os
import inspect
import sys
import uuid
import importlib.util
import hashlib

from .logger import Logger

def _find_python_scripts(path):
	try: path_files = os.listdir(path)
	except FileNotFoundError:
		Logger.warning(f"Unable to find directory '{path}', skipping...")
		return list()

	files = [
		os.path.join(path, f) for f in path_files
			if os.path.isfile(os.path.join(path, f))
			and not f.startswith("__")
			and f.endswith(".py")
	]

	dirs = [
		d for d in path_files
			if os.path.isdir(os.path.join(path, d))
	]

	for d in dirs:
		new_path = os.path.join(path, d)
		new_files = _find_python_scripts(new_path)
		files.extend(new_files)

	return files


def load_dir(path):
	Logger.info(f"Loading scripts at '{path}'")
	files = _find_python_scripts(path)
	if not path in sys.path:
		sys.path.insert(0, path)

	loaded = list()
	for file_path in files:
		random_name = str(uuid.uuid1())

		try:
			spec = importlib.util.spec_from_file_location(random_name, file_path)
			module = importlib.util.module_from_spec(spec)
			spec.loader.exec_module(module)

			if hasattr(module, 'pavao_endpoint'):
				callback = module.pavao_endpoint
				if inspect.isfunction(callback):

					with open(file_path, 'rb') as fd:
						hasher = hashlib.md5()
						hasher.update(fd.read())
						file_hash = hasher.hexdigest()

						loaded.append((file_path, file_hash, callback))
						Logger.info(f"Loaded endpoint file {file_path}")

		except Exception as e:
			Logger.warning(f"Unable to load file '{file_path}': {e}")
			continue

	return loaded

#-------------------------------------------------------------------------------

__all__ = [
	"load_dir"
]

