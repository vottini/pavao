
import sys
sys.path.append('..')

import os
import pytest
import pavao.config as cfg
from pavao.config import ConfigException, load_settings, unflatten, process_config

#-------------------------------------------------------------------------------
# unflatten

def testUnflattenSimple():
	assert unflatten({"a.b": 1, "a.c": 2}) == {"a": {"b": 1, "c": 2}}

def testUnflattenDeep():
	assert unflatten({"a.b.c": 42}) == {"a": {"b": {"c": 42}}}

def testUnflattenMixedFlatAndNested():
	result = unflatten({"a": {"x": 1}, "a.y": 2})
	assert result["a"]["x"] == 1
	assert result["a"]["y"] == 2

def testUnflattenDoesNotMutateInput():
	original_nested = {"x": 1}
	config = {"a": original_nested, "a.y": 2}
	unflatten(config)
	assert original_nested == {"x": 1}

def testUnflattenConflictRaises():
	with pytest.raises(ConfigException):
		unflatten({"a": "scalar", "a.b": 1})

def testUnflattenEmptyDict():
	assert unflatten({}) == {}

#-------------------------------------------------------------------------------
# load_settings: empty / None YAML

def testLoadEmptyYamlReturnsSettings(tmp_path):
	f = tmp_path / "empty.yml"
	f.write_text("")
	settings = load_settings(str(f))
	assert settings.get_setting("anything", "default") == "default"

def testLoadIsDefaultMissingFile(tmp_path):
	settings = load_settings(str(tmp_path / "nope.yml"), is_default=True)
	assert settings.get_setting("x", "default") == "default"

def testLoadNonExistentRaises(tmp_path):
	with pytest.raises(ConfigException):
		load_settings(str(tmp_path / "nope.yml"), is_default=False)

def testLoadBadYamlRaises(tmp_path):
	f = tmp_path / "bad.yml"
	f.write_text("key: [unclosed")
	with pytest.raises(ConfigException):
		load_settings(str(f))

#-------------------------------------------------------------------------------
# get_setting: mid-walk scalar guard

def testGetSettingMidWalkScalar(tmp_path):
	f = tmp_path / "cfg.yml"
	f.write_text("a: scalar\n")
	settings = load_settings(str(f))
	# 'a' is a scalar, not a dict — walking 'a.b' must not AttributeError
	assert settings.get_setting("a.b", "default") == "default"

def testGetSettingMissingTopLevelReturnsNone(tmp_path):
	f = tmp_path / "cfg.yml"
	f.write_text("a: 1\n")
	settings = load_settings(str(f))
	assert settings.get_setting("nonexistent", str) is None

#-------------------------------------------------------------------------------
# process_config: required sub-fields raise, optional top-level returns None

def testMissingRequiredSubFieldRaises(tmp_path):
	f = tmp_path / "cfg.yml"
	f.write_text("db:\n  host: localhost\n")
	settings = load_settings(str(f))
	schema = {"host": str, "port": int}
	with pytest.raises(ConfigException, match="required"):
		settings.get_setting("db", schema)

def testMissingOptionalTopLevelReturnsNone(tmp_path):
	f = tmp_path / "cfg.yml"
	f.write_text("a: 1\n")
	settings = load_settings(str(f))
	assert settings.get_setting("missing", str) is None

#-------------------------------------------------------------------------------
# env var interpolation

def testEnvVarFullSubstitution(tmp_path, monkeypatch):
	monkeypatch.setenv("MY_PORT", "8080")
	f = tmp_path / "cfg.yml"
	f.write_text("port: ${MY_PORT}\n")
	settings = load_settings(str(f))
	assert settings.get_setting("port", int) == 8080

def testEnvVarStringInterpolation(tmp_path, monkeypatch):
	monkeypatch.setenv("HOST", "localhost")
	f = tmp_path / "cfg.yml"
	f.write_text("addr: 'http://${HOST}/api'\n")
	settings = load_settings(str(f))
	assert settings.get_setting("addr", str) == "http://localhost/api"

def testEnvVarMultipleInOneValue(tmp_path, monkeypatch):
	monkeypatch.setenv("HOST", "db.internal")
	monkeypatch.setenv("PORT", "5432")
	f = tmp_path / "cfg.yml"
	f.write_text("dsn: '${HOST}:${PORT}'\n")
	settings = load_settings(str(f))
	assert settings.get_setting("dsn", str) == "db.internal:5432"

def testEnvVarMissingRaises(tmp_path, monkeypatch):
	monkeypatch.delenv("GHOST_VAR", raising=False)
	f = tmp_path / "cfg.yml"
	f.write_text("x: ${GHOST_VAR}\n")
	settings = load_settings(str(f))
	with pytest.raises(ConfigException, match="GHOST_VAR"):
		settings.get_setting("x", str)

def testEnvVarBadCastRaises(tmp_path, monkeypatch):
	monkeypatch.setenv("MY_VAL", "notanint")
	f = tmp_path / "cfg.yml"
	f.write_text("port: ${MY_VAL}\n")
	settings = load_settings(str(f))
	with pytest.raises(ConfigException):
		settings.get_setting("port", int)

#-------------------------------------------------------------------------------
# type coercion and schema defaults

def testSchemaDefaultReturnedWhenKeyAbsent(tmp_path):
	f = tmp_path / "cfg.yml"
	f.write_text("other: 1\n")
	settings = load_settings(str(f))
	assert settings.get_setting("missing", "my_default") == "my_default"

def testWrongTypeRaises(tmp_path):
	f = tmp_path / "cfg.yml"
	f.write_text("count: hello\n")
	settings = load_settings(str(f))
	with pytest.raises(ConfigException):
		settings.get_setting("count", int)

def testListOfDicts(tmp_path):
	f = tmp_path / "cfg.yml"
	f.write_text("items:\n  - name: foo\n  - name: bar\n")
	settings = load_settings(str(f))
	result = settings.get_setting("items", [{"name": str}])
	assert result == [{"name": "foo"}, {"name": "bar"}]

def testListExpectedButScalarGiven(tmp_path):
	f = tmp_path / "cfg.yml"
	f.write_text("items: scalar\n")
	settings = load_settings(str(f))
	with pytest.raises(ConfigException):
		settings.get_setting("items", [str])

def testScalarExpectedButListGiven(tmp_path):
	f = tmp_path / "cfg.yml"
	f.write_text("items:\n  - a\n  - b\n")
	settings = load_settings(str(f))
	with pytest.raises(ConfigException):
		settings.get_setting("items", str)

#-------------------------------------------------------------------------------

if __name__ == "__main__":
	import tempfile, pathlib
	with tempfile.TemporaryDirectory() as d:
		tmp = pathlib.Path(d)
		testUnflattenSimple()
		testUnflattenDeep()
		testUnflattenEmptyDict()
		testLoadEmptyYamlReturnsSettings(tmp)
		testLoadIsDefaultMissingFile(tmp)
