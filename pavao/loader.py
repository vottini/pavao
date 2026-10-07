
import os
import inspect
import sys
import uuid
import time
import importlib.util

from .logger import Logger
from .utils import remove_prefix
from .exception import PavaoException

class LoaderException(PavaoException):
	pass

#-------------------------------------------------------------------------------

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
		new_files = _find_python_scripts(os.path.join(path, d))
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

	filtered = {
		dep: dependees - {abs_path}
		for dep, dependees in _dependents.items()
		if len(dependees - {abs_path}) > 0
	}

	_dependents = filtered

#-------------------------------------------------------------------------------

def _exec_module(abs_path):
	spec = importlib.util.spec_from_file_location(str(uuid.uuid4()), abs_path)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


def load_script(full_path, common_path, verbose):
	abs_path = os.path.abspath(full_path)
	module_path = remove_prefix(full_path, common_path)
	clear_dependencies(abs_path)

	try:
		return _exec_module(abs_path)
	except Exception as e:
		Logger.warning(f"Unable to load file '{module_path}': {e}")
		return None


def load_folder(dir_path, verbose=True):
	for file_path in _find_python_scripts(dir_path):
		load_script(file_path, dir_path, verbose)

#-------------------------------------------------------------------------------

loadable_methods = [
	('SERVICE',  'pavao_service',  'service'),
	('ENDPOINT', 'pavao_endpoint', 'endpoint'),
	('TASK',     'pavao_task',     'task')
]

def load_component(full_path, common_path, verbose):
	abs_path = os.path.abspath(full_path)
	module_path = remove_prefix(full_path, common_path)
	clear_dependencies(abs_path)

	try:
		module = _exec_module(abs_path)

		for tag, method, type_str in loadable_methods:
			if hasattr(module, method):
				candidate = getattr(module, method)
				if inspect.isfunction(candidate):
					if verbose:
						Logger.info(f"Loaded {type_str} file {module_path}")
					return tag, candidate

	except Exception as e:
		Logger.warning(f"Unable to load file '{module_path}': {e}")
		return None


def load_components_dir(dir_path, verbose):
	files = _find_python_scripts(dir_path)
	if dir_path not in sys.path:
		sys.path.insert(0, dir_path)

	loaded = list()
	for file_path in files:
		specifier = load_component(file_path, dir_path, verbose)
		if specifier is not None:
			loaded.append((file_path, specifier))

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
	try:
		with open(abs_path) as fd:
			return fd.read()
	except OSError:
		raise LoaderException(f"Unable to read file '{abs_path}'") from None

#-------------------------------------------------------------------------------

_loaded_modules = dict()

def load_module(abs_path):
	module = _exec_module(abs_path)
	_loaded_modules[abs_path] = {'timestamp': time.time(), 'module': module}
	return module


def _retrieve_or_load_module(abs_path):
	if (entry := _loaded_modules.get(abs_path)) is not None:
		if entry['timestamp'] > os.path.getmtime(abs_path):
			return entry['module']
	return load_module(abs_path)


def import_module(module_name, with_name=None):
	if os.path.sep in module_name:
		raise LoaderException("Invalid module name")

	caller_dir, caller_script = get_caller_path()
	path_to_module = module_name.replace('.', os.path.sep) + ".py"
	abs_path = os.path.abspath(os.path.join(caller_dir, path_to_module))
	module = _retrieve_or_load_module(abs_path)

	requester = os.path.join(caller_dir, caller_script)
	add_dependency(abs_path, requester)

	target_name = module_name if with_name is None else with_name
	inspect.stack()[1].frame.f_globals[target_name] = module


class ImportedModule:
	def __init__(self, module, scope):
		self.module = module
		self.scope = scope

	def import_item(self, item, with_name=None):
		if not hasattr(self.module, item):
			raise LoaderException(
				f"Module '{self.module.__spec__.origin}' has no attribute '{item}'"
			)
		item_name = item if with_name is None else with_name
		self.scope[item_name] = getattr(self.module, item)
		return self


def from_module(relative_path):
	caller_dir, caller_script = get_caller_path()
	full_path = relative_path if relative_path.endswith('.py') else f"{relative_path}.py"
	abs_path = os.path.abspath(os.path.join(caller_dir, full_path))
	module = _retrieve_or_load_module(abs_path)

	requester = os.path.join(caller_dir, caller_script)
	add_dependency(abs_path, requester)

	return ImportedModule(module, inspect.stack()[1].frame.f_globals)

#-------------------------------------------------------------------------------

def _reset_state():
	global _dependents, _loaded_modules
	_dependents = dict()
	_loaded_modules = dict()

#-------------------------------------------------------------------------------

__all__ = [
	"LoaderException",
	"retrieve_dependees",
	"load_component",
	"load_components_dir",
	"load_folder",
	"path_to",
	"include",
	"load_module",
	"import_module",
	"from_module"
]
