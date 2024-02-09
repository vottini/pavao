
import os
import inspect
import sys
import uuid
import importlib.util
from datetime import datetime

from .logger import Logger

def _find_python_scripts(path):
	try: path_files = os.listdir(path)
	except FileNotFoundError:
		Logger.warning(f"Unable to find directory '{path}', skipping...")
		return list()

	files = [
		os.path.join(path, file) for file in path_files
			if os.path.isfile(os.path.join(path, file))
			and not file.startswith("__")
			and file.endswith(".py")
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

#-------------------------------------------------------------------------------

_dependents = dict()
def retrieve_dependees(dependency):
	return _dependents.get(dependency, set())


def add_dependency(dependency, dependee):
	dependees = _dependents.get(dependency, set())
	dependees.add(dependee)
	_dependents[dependency] = dependees


def clear_dependencies(abs_path):
	global _dependents

	filtered = dict()
	to_exclude = set([abs_path])
	for dependency, dependees in _dependents.items():
		filtered_dependents = dependees - to_exclude

		if len(filtered_dependents) > 0:
			filtered[dependency] = filtered_dependents

	_dependents = filtered

#-------------------------------------------------------------------------------

def load_file(file_path):
	abs_path = os.path.abspath(file_path)
	clear_dependencies(abs_path)

	try:
		random_name = str(uuid.uuid1())
		spec = importlib.util.spec_from_file_location(random_name, abs_path)
		module = importlib.util.module_from_spec(spec)
		spec.loader.exec_module(module)

		if hasattr(module, 'pavao_endpoint'):
			specifier = module.pavao_endpoint

			if inspect.isfunction(specifier):
				Logger.info(f"Loaded endpoint file {abs_path}")
				return specifier

	except Exception as e:
		Logger.warning(f"Unable to load file '{abs_path}': {e}")
		return None


def load_dir(path):
	Logger.info(f"Loading scripts at '{path}'")
	files = _find_python_scripts(path)
	if not path in sys.path:
		sys.path.insert(0, path)

	loaded = list()
	for file_path in files:
		full_path = os.path.join(path, file_path)
		specifier = load_file(full_path)

		if specifier is not None:
			loaded.append((full_path, specifier))

	return loaded

#-------------------------------------------------------------------------------

def get_caller_path():
	caller_frame = inspect.stack()[2]
	caller_path = os.path.abspath(caller_frame.filename)

	return (
		os.path.dirname(caller_path),
		os.path.basename(caller_path),
	)


def path_to(filename):
	caller_dir, caller_script = get_caller_path()
	requester = os.path.join(caller_dir, caller_script)
	abs_path = os.path.join(caller_dir, filename)
	add_dependency(abs_path, requester)
	return abs_path


def include(filename):
	caller_dir, caller_script = get_caller_path()
	requester = os.path.join(caller_dir, caller_script)
	abs_path = os.path.join(caller_dir, filename)
	add_dependency(abs_path, requester)
	with open(abs_path) as fd:
		return fd.read()

#-------------------------------------------------------------------------------

_loaded_modules = dict()

class ImportedModule:
	def __init__(self, module, scope):
		self.module = module
		self.scope = scope

	def import_item(self, item):
		self.scope[item] = getattr(self.module, item)
		return self


def _load_module(abs_path):
	if (loaded_module := _loaded_modules.get(abs_path)) is not None:
		modification_timestamp = os.path.getmtime(abs_path)
		if loaded_module['timestamp'] > modification_timestamp:
			return loaded_module['module']

	random_name = str(uuid.uuid1())
	spec = importlib.util.spec_from_file_location(random_name, abs_path)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)

	_loaded_modules[abs_path] = {
		'timestamp': datetime.now().timestamp(),
		'module': module
	}

	return module


def import_module(module_name):
	if os.path.sep in module_name:
		raise Exception("Invalid module name")

	caller_dir, caller_script = get_caller_path()
	path_to_module = module_name.replace('.', os.path.sep) + ".py"
	complete_path = os.path.join(caller_dir, path_to_module)
	abs_path = os.path.abspath(complete_path)
	module = _load_module(abs_path)

	requester = os.path.join(caller_dir, caller_script)
	add_dependency(abs_path, requester)

	previous_frame = inspect.stack()[1].frame
	previous_frame.f_globals[module_name] = module


def from_module(relative_path):
	caller_dir, caller_script = get_caller_path()
	full_path = (relative_path if relative_path.endswith('.py')
		else f"{relative_path}.py")

	file_path = os.path.join(caller_dir, full_path)
	abs_path = os.path.abspath(file_path)
	module = _load_module(abs_path)

	requester = os.path.join(caller_dir, caller_script)
	add_dependency(abs_path, requester)

	previous_frame = inspect.stack()[1].frame
	return ImportedModule(module, previous_frame.f_globals)

#-------------------------------------------------------------------------------

__all__ = [
	"retrieve_dependees",
	"load_file",
	"load_dir",
	"path_to",
	"include",
	"import_module",
	"from_module"
]

