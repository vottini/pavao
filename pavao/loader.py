
import os
import inspect
import sys
import importlib.util
import uuid

import logger

def _find_python_scripts(path):
	path_files = os.listdir(path)

	files = [
		os.path.join(path, f) for f in path_files
			if os.path.isfile(os.path.join(path, f))
			and not f.startswith("_")
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
					loaded.append(callback)

		except Exception as e:
			logger.warning(f"Unable to load file '{file_path}': {e}")
			continue

	return loaded

