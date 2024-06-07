
import os
import inspect
import sys
import uuid
import importlib.util
from datetime import datetime

from .logger import Logger
from .utils import remove_prefix

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

loadable_methods = [
	('SERVICE', 'pavao_service', 'service'),
	('ENDPOINT', 'pavao_endpoint', 'endpoint'),
	('TASK', 'pavao_task', 'task')
]

def load_file(full_path, common_path, verbose):
	abs_path = os.path.abspath(full_path)
	module_path = remove_prefix(full_path, common_path)
	clear_dependencies(abs_path)

	try:
		random_name = str(uuid.uuid1())
		spec = importlib.util.spec_from_file_location(random_name, abs_path)
		module = importlib.util.module_from_spec(spec)
		spec.loader.exec_module(module)

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


def load_dir(dir_path, verbose):
	files = _find_python_scripts(dir_path)
	if not dir_path in sys.path:
		sys.path.insert(0, dir_path)

	loaded = list()
	for file_path in files:
		full_path = os.path.join(dir_path, file_path)
		specifier = load_file(full_path, dir_path, verbose)

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

def load_module(abs_path):
	random_name = str(uuid.uuid1())
	spec = importlib.util.spec_from_file_location(random_name, abs_path)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)

	_loaded_modules[abs_path] = {
		'timestamp': datetime.now().timestamp(),
		'module': module
	}

	return module


def _retrieve_or_load_module(abs_path):
	if (loaded_module := _loaded_modules.get(abs_path)) is not None:
		modification_timestamp = os.path.getmtime(abs_path)
		if loaded_module['timestamp'] > modification_timestamp:
			return loaded_module['module']

	return load_module(abs_path)


def import_module(module_name):
	if os.path.sep in module_name:
		raise Exception("Invalid module name")

	caller_dir, caller_script = get_caller_path()
	path_to_module = module_name.replace('.', os.path.sep) + ".py"
	complete_path = os.path.join(caller_dir, path_to_module)
	abs_path = os.path.abspath(complete_path)
	module = _retrieve_or_load_module(abs_path)

	requester = os.path.join(caller_dir, caller_script)
	add_dependency(abs_path, requester)

	previous_frame = inspect.stack()[1].frame
	previous_frame.f_globals[module_name] = module


class ImportedModule:
	def __init__(self, module, scope):
		self.module = module
		self.scope = scope

	def import_item(self, item):
		self.scope[item] = getattr(self.module, item)
		return self


def from_module(relative_path):
	caller_dir, caller_script = get_caller_path()
	full_path = (relative_path if relative_path.endswith('.py')
		else f"{relative_path}.py")

	file_path = os.path.join(caller_dir, full_path)
	abs_path = os.path.abspath(file_path)
	module = _retrieve_or_load_module(abs_path)

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
	"load_module",
	"import_module",
	"from_module"
]

