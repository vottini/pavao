
import sys
sys.path.append('..')

import os
import time
import pytest
import pavao.loader as _loader_mod
from pavao.loader import (
	LoaderException,
	_find_python_scripts,
	_reset_state,
	add_dependency,
	retrieve_dependees,
	clear_dependencies,
	load_script,
	load_folder,
	load_component,
	load_components_dir,
	load_module,
	_retrieve_or_load_module,
	include,
	import_module,
	from_module,
	ImportedModule,
)

#-------------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_state():
	_reset_state()
	yield
	_reset_state()

#-------------------------------------------------------------------------------
# _find_python_scripts

def testFindScriptsLocatesFiles(tmp_path):
	(tmp_path / "a.py").write_text("x = 1")
	(tmp_path / "b.py").write_text("x = 2")
	(tmp_path / "notes.txt").write_text("ignored")

	found = _find_python_scripts(str(tmp_path))
	names = {os.path.basename(p) for p in found}
	assert names == {"a.py", "b.py"}

def testFindScriptsSkipsDunderFiles(tmp_path):
	(tmp_path / "__init__.py").write_text("")
	(tmp_path / "__main__.py").write_text("")
	(tmp_path / "real.py").write_text("")

	found = _find_python_scripts(str(tmp_path))
	assert all("__" not in os.path.basename(p) for p in found)

def testFindScriptsRecursesSubdirs(tmp_path):
	sub = tmp_path / "sub"
	sub.mkdir()
	(tmp_path / "top.py").write_text("")
	(sub / "nested.py").write_text("")

	found = _find_python_scripts(str(tmp_path))
	names = {os.path.basename(p) for p in found}
	assert "top.py" in names
	assert "nested.py" in names

def testFindScriptsMissingDirReturnsEmpty():
	found = _find_python_scripts("/nonexistent/path/xyz")
	assert found == []

#-------------------------------------------------------------------------------
# dependency tracking

def testAddAndRetrieveDependency():
	add_dependency("/dep.py", "/user.py")
	assert "/user.py" in retrieve_dependees("/dep.py")

def testMultipleDependees():
	add_dependency("/dep.py", "/a.py")
	add_dependency("/dep.py", "/b.py")
	assert retrieve_dependees("/dep.py") == {"/a.py", "/b.py"}

def testClearDependenciesRemovesDependee():
	add_dependency("/dep.py", "/user.py")
	clear_dependencies("/user.py")
	assert "/user.py" not in retrieve_dependees("/dep.py")

def testClearDependenciesKeepsOtherDependees():
	add_dependency("/dep.py", "/a.py")
	add_dependency("/dep.py", "/b.py")
	clear_dependencies("/a.py")
	assert "/b.py" in retrieve_dependees("/dep.py")

def testRetrieveMissingDependencyReturnsEmpty():
	assert retrieve_dependees("/nobody.py") == set()

#-------------------------------------------------------------------------------
# load_script

def testLoadScriptReturnsModule(tmp_path):
	f = tmp_path / "mod.py"
	f.write_text("value = 42")
	module = load_script(str(f), str(tmp_path), verbose=False)
	assert module is not None
	assert module.value == 42

def testLoadScriptSyntaxErrorReturnsNone(tmp_path):
	f = tmp_path / "bad.py"
	f.write_text("def broken(: pass")
	result = load_script(str(f), str(tmp_path), verbose=False)
	assert result is None

#-------------------------------------------------------------------------------
# load_component

def testLoadComponentEndpoint(tmp_path):
	f = tmp_path / "ep.py"
	f.write_text("def pavao_endpoint(): return 'hello'")
	result = load_component(str(f), str(tmp_path), verbose=False)
	assert result is not None
	tag, fn = result
	assert tag == "ENDPOINT"
	assert fn() == "hello"

def testLoadComponentService(tmp_path):
	f = tmp_path / "svc.py"
	f.write_text("def pavao_service(): pass")
	tag, _ = load_component(str(f), str(tmp_path), verbose=False)
	assert tag == "SERVICE"

def testLoadComponentTask(tmp_path):
	f = tmp_path / "tsk.py"
	f.write_text("def pavao_task(): pass")
	tag, _ = load_component(str(f), str(tmp_path), verbose=False)
	assert tag == "TASK"

def testLoadComponentNoMarkerReturnsNone(tmp_path):
	f = tmp_path / "plain.py"
	f.write_text("def some_function(): pass")
	assert load_component(str(f), str(tmp_path), verbose=False) is None

def testLoadComponentSyntaxErrorReturnsNone(tmp_path):
	f = tmp_path / "bad.py"
	f.write_text("def broken(: pass")
	assert load_component(str(f), str(tmp_path), verbose=False) is None

def testLoadComponentNonFunctionMarkerReturnsNone(tmp_path):
	f = tmp_path / "notfn.py"
	f.write_text("pavao_endpoint = 'not a function'")
	assert load_component(str(f), str(tmp_path), verbose=False) is None

#-------------------------------------------------------------------------------
# load_components_dir

def testLoadComponentsDirFindsAll(tmp_path):
	(tmp_path / "a.py").write_text("def pavao_endpoint(): return 'A'")
	(tmp_path / "b.py").write_text("def pavao_endpoint(): return 'B'")
	(tmp_path / "skip.py").write_text("x = 1")

	loaded = load_components_dir(str(tmp_path), verbose=False)
	assert len(loaded) == 2
	results = {fn() for _, (_, fn) in loaded}
	assert results == {"A", "B"}

def testLoadComponentsDirSkipsBrokenFiles(tmp_path):
	(tmp_path / "good.py").write_text("def pavao_endpoint(): return 'ok'")
	(tmp_path / "bad.py").write_text("def broken(: pass")

	loaded = load_components_dir(str(tmp_path), verbose=False)
	assert len(loaded) == 1

def testLoadComponentsDirMissingDirReturnsEmpty():
	loaded = load_components_dir("/nonexistent/xyz", verbose=False)
	assert loaded == []

def testLoadComponentsDirNoBugOnDoubleJoin(tmp_path):
	# regression: previously did os.path.join(dir_path, file_path) where
	# file_path was already a full path, producing dir_path/dir_path/file.py
	sub = tmp_path / "sub"
	sub.mkdir()
	(sub / "ep.py").write_text("def pavao_endpoint(): return 'nested'")

	loaded = load_components_dir(str(tmp_path), verbose=False)
	assert len(loaded) == 1
	_, (_, fn) = loaded[0]
	assert fn() == "nested"

#-------------------------------------------------------------------------------
# load_module / _retrieve_or_load_module

def testLoadModuleExecutesAndCaches(tmp_path):
	f = tmp_path / "mod.py"
	f.write_text("value = 99")
	module = load_module(str(f))
	assert module.value == 99

def testRetrieveOrLoadUsesCache(tmp_path):
	f = tmp_path / "mod.py"
	f.write_text("value = 1")
	m1 = load_module(str(f))
	m2 = _retrieve_or_load_module(str(f))
	assert m1 is m2

def testRetrieveOrLoadReloadsWhenStale(tmp_path):
	f = tmp_path / "mod.py"
	f.write_text("value = 1")
	m1 = load_module(str(f))

	import pavao.loader as lm
	# backdate the cache entry to before the file's current mtime
	lm._loaded_modules[str(f)]['timestamp'] = os.path.getmtime(str(f)) - 1

	m2 = _retrieve_or_load_module(str(f))
	# module_from_spec always allocates a new object — if m2 is not m1,
	# _retrieve_or_load_module correctly discarded the stale cache entry
	assert m2 is not m1

#-------------------------------------------------------------------------------

#-------------------------------------------------------------------------------
# ImportedModule

def testImportItemInjectsIntoScope(tmp_path):
	from pavao.loader import ImportedModule
	f = tmp_path / "mod.py"
	f.write_text("answer = 42")
	module = load_module(str(f))
	scope = {}
	ImportedModule(module, scope).import_item("answer")
	assert scope["answer"] == 42

def testImportItemWithRename(tmp_path):
	from pavao.loader import ImportedModule
	f = tmp_path / "mod.py"
	f.write_text("answer = 42")
	module = load_module(str(f))
	scope = {}
	ImportedModule(module, scope).import_item("answer", with_name="result")
	assert scope["result"] == 42
	assert "answer" not in scope

def testImportItemMissingRaisesLoaderException(tmp_path):
	from pavao.loader import ImportedModule
	f = tmp_path / "mod.py"
	f.write_text("x = 1")
	module = load_module(str(f))
	with pytest.raises(LoaderException, match="no attribute 'missing'"):
		ImportedModule(module, {}).import_item("missing")

def testImportItemChaining(tmp_path):
	from pavao.loader import ImportedModule
	f = tmp_path / "mod.py"
	f.write_text("a = 1\nb = 2")
	module = load_module(str(f))
	scope = {}
	ImportedModule(module, scope).import_item("a").import_item("b")
	assert scope["a"] == 1 and scope["b"] == 2

#-------------------------------------------------------------------------------
# load_folder

def testLoadFolderLoadsAllScripts(tmp_path):
	(tmp_path / "a.py").write_text("val_a = 1")
	(tmp_path / "b.py").write_text("val_b = 2")
	load_folder(str(tmp_path), verbose=False)  # must not raise

def testLoadFolderSkipsBrokenFiles(tmp_path):
	(tmp_path / "bad.py").write_text("def broken(: pass")
	load_folder(str(tmp_path), verbose=False)  # must not raise

#-------------------------------------------------------------------------------
# load_component verbose path

def testLoadComponentVerboseLogsAndReturns(tmp_path):
	f = tmp_path / "ep.py"
	f.write_text("def pavao_endpoint(): return 'ok'")
	result = load_component(str(f), str(tmp_path), verbose=True)
	assert result is not None
	tag, fn = result
	assert tag == "ENDPOINT"

#-------------------------------------------------------------------------------
# include

@pytest.fixture
def patched_caller(tmp_path, monkeypatch):
	monkeypatch.setattr(_loader_mod, 'get_caller_path',
		lambda: (str(tmp_path), 'caller.py'))
	return tmp_path

def testIncludeReturnsFileContents(patched_caller):
	(patched_caller / "tmpl.html").write_text("<h1>hi</h1>")
	assert include("tmpl.html") == "<h1>hi</h1>"

def testIncludeRegistersDependency(patched_caller):
	f = patched_caller / "tmpl.html"
	f.write_text("content")
	include("tmpl.html")
	requester = str(patched_caller / "caller.py")
	assert requester in retrieve_dependees(str(f))

def testIncludeMissingFileRaisesLoaderException(patched_caller):
	with pytest.raises(LoaderException):
		include("nonexistent.html")

#-------------------------------------------------------------------------------
# import_module

def testImportModuleRaisesOnPathSeparator():
	with pytest.raises(LoaderException):
		import_module("some/path")

def testImportModuleInjectsIntoCallerGlobals(patched_caller):
	(patched_caller / "mymod.py").write_text("value = 123")
	import_module("mymod")
	try:
		assert globals()["mymod"].value == 123
	finally:
		globals().pop("mymod", None)

def testImportModuleWithRenameUsesGivenName(patched_caller):
	(patched_caller / "mymod.py").write_text("value = 456")
	import_module("mymod", with_name="_renamed_mod")
	try:
		assert globals()["_renamed_mod"].value == 456
	finally:
		globals().pop("_renamed_mod", None)

def testImportModuleRegistersDependency(patched_caller):
	f = patched_caller / "mymod.py"
	f.write_text("x = 1")
	import_module("mymod")
	globals().pop("mymod", None)
	requester = str(patched_caller / "caller.py")
	assert requester in retrieve_dependees(str(f))

#-------------------------------------------------------------------------------
# from_module

def testFromModuleReturnsImportedModule(patched_caller):
	(patched_caller / "mymod.py").write_text("value = 789")
	result = from_module("mymod")
	assert isinstance(result, ImportedModule)
	assert result.module.value == 789

def testFromModuleAddsExtensionIfMissing(patched_caller):
	(patched_caller / "mymod.py").write_text("value = 1")
	result = from_module("mymod")
	assert result.module.value == 1

def testFromModuleAcceptsExplicitExtension(patched_caller):
	(patched_caller / "mymod.py").write_text("value = 2")
	result = from_module("mymod.py")
	assert result.module.value == 2

def testFromModuleScopeIsCallerGlobals(patched_caller):
	(patched_caller / "mymod.py").write_text("val = 99")
	result = from_module("mymod")
	result.import_item("val", with_name="_from_mod_val")
	try:
		assert globals()["_from_mod_val"] == 99
	finally:
		globals().pop("_from_mod_val", None)

def testFromModuleRegistersDependency(patched_caller):
	f = patched_caller / "mymod.py"
	f.write_text("x = 1")
	from_module("mymod")
	requester = str(patched_caller / "caller.py")
	assert requester in retrieve_dependees(str(f))

#-------------------------------------------------------------------------------

if __name__ == "__main__":
	import tempfile, pathlib
	with tempfile.TemporaryDirectory() as d:
		tmp = pathlib.Path(d)
		testFindScriptsLocatesFiles(tmp)
		testLoadComponentEndpoint(tmp)
		testLoadComponentsDirFindsAll(tmp)
