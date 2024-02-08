
import os
import inspect
import sys
import uuid
import importlib.util

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


def load_file(file_path):
	random_name = str(uuid.uuid1())

	try:
		spec = importlib.util.spec_from_file_location(random_name, file_path)
		module = importlib.util.module_from_spec(spec)
		spec.loader.exec_module(module)

		if hasattr(module, 'pavao_endpoint'):
			specifier = module.pavao_endpoint

			if inspect.isfunction(specifier):
				Logger.info(f"Loaded endpoint file {file_path}")
				return specifier

	except Exception as e:
		Logger.warning(f"Unable to load file '{file_path}': {e}")
		return None


def load_dir(path):
	Logger.info(f"Loading scripts at '{path}'")
	files = _find_python_scripts(path)
	if not path in sys.path:
		sys.path.insert(0, path)

	loaded = list()
	for file_path in files:
		specifier = load_file(file_path)

		if specifier is not None:
			loaded.append((file_path, specifier))

	return loaded

#-------------------------------------------------------------------------------

def get_caller_dir():
	caller_frame = inspect.stack()[2]
	caller_path = os.path.abspath(caller_frame.filename)
	return os.path.dirname(caller_path)


def path_to(filename):
	caller_dir = get_caller_dir()
	return os.path.join(caller_dir, filename)


def include(filename):
	caller_dir = get_caller_dir()
	filepath = os.path.join(caller_dir, filename)
	with open(filepath) as fd:
		return fd.read()

#-------------------------------------------------------------------------------

class ImportedModule:
	def __init__(self, module, scope):
		self.module = module
		self.scope = scope

	def import_item(self, item):
		self.scope[item] = getattr(self.module, item)
		return self


def _load_module(caller_dir, module_name):
	file_path = os.path.join(caller_dir, f"{module_name}.py")
	spec = importlib.util.spec_from_file_location(module_name, file_path)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


def import_module(module_name):
	module = _load_module(get_caller_dir(), module_name)
	previous_frame = inspect.stack()[1].frame
	previous_frame.f_globals[module_name] = module


def from_module(module_name):
	module = _load_module(get_caller_dir(), module_name)
	previous_frame = inspect.stack()[1].frame
	return ImportedModule(module, previous_frame.f_globals)

#-------------------------------------------------------------------------------

__all__ = [
	"load_file",
	"load_dir",
	"path_to",
	"include",
	"import_module",
	"from_module"
]

