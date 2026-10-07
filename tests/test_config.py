
import sys
sys.path.append('..')

import os
import pytest
import pavao
from pavao.config import ConfigException, load_settings, unflatten, process_config

@pytest.fixture(autouse=True)
def db_env(monkeypatch):
	monkeypatch.setenv("DB_NAME", "testdb")
	monkeypatch.setenv("DB_ROLE", "testuser")

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
# load_settings

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

def testBadFiles():
	for bad_file in ["configs/non_existent_file.yml", "configs/bad_file.yml"]:
		with pytest.raises(pavao.config.ConfigException):
			pavao.config.load_settings(bad_file)

#-------------------------------------------------------------------------------
# get_setting: navigation

def testGetSettingMidWalkScalar(tmp_path):
	f = tmp_path / "cfg.yml"
	f.write_text("a: scalar\n")
	settings = load_settings(str(f))
	assert settings.get_setting("a.b", "default") == "default"

def testGetSettingMissingTopLevelReturnsNone(tmp_path):
	f = tmp_path / "cfg.yml"
	f.write_text("a: 1\n")
	settings = load_settings(str(f))
	assert settings.get_setting("nonexistent", str) is None

#-------------------------------------------------------------------------------
# process_config: required and optional

def testMissingRequiredSubFieldRaises(tmp_path):
	f = tmp_path / "cfg.yml"
	f.write_text("db:\n  host: localhost\n")
	settings = load_settings(str(f))
	with pytest.raises(ConfigException, match="required"):
		settings.get_setting("db", {"host": str, "port": int})

def testMissingOptionalTopLevelReturnsNone(tmp_path):
	f = tmp_path / "cfg.yml"
	f.write_text("a: 1\n")
	settings = load_settings(str(f))
	assert settings.get_setting("missing", str) is None

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
# fixture-file based tests

databaseSchema = {
	"name": str,
	"user": str,
	"address": {
		"port": 3322,
		"ip": {
			"hostname": str,
			"version": 4
		},
		"extra": {
			"foo": "bar",
			"john": "doe"
		}
	},
}

localizationSchema = {
	"keyboard": str,
	"variation": {
		"country": str,
		"dialect": str
	}
}

giantsSchema = [str]

servicesSchema = [{"name": str, "url": str, "prefix": "/api"}]

positionSchema = {"latitude": float, "longitude": float, "accuracy": 10.0}

def testMissing():
	for file in ["missing_type.yml", "missing_dict.yml"]:
		with pytest.raises(pavao.config.ConfigException):
			settings = pavao.config.load_settings("configs/" + file)
			settings.get_setting("pavao.database", databaseSchema)

def testArrays():
	settings = pavao.config.load_settings("configs/array_incompat.yml")
	for test in [("localization", localizationSchema), ("giants", giantsSchema)]:
		with pytest.raises(pavao.config.ConfigException):
			settings.get_setting(*test)

	settings = pavao.config.load_settings("configs/correct.yml")
	for bad_schema in [[str, int], [(str, int)]]:
		with pytest.raises(pavao.config.ConfigException):
			settings.get_setting("giants", bad_schema)

def testVariables():
	settings = pavao.config.load_settings("configs/missing_var.yml")
	for test in [("pavao.database", databaseSchema), ("position", positionSchema)]:
		with pytest.raises(pavao.config.ConfigException):
			settings.get_setting(*test)

def testTypes():
	settings = pavao.config.load_settings("configs/bad_types.yml")
	for test in [("position1", positionSchema), ("position2", positionSchema)]:
		with pytest.raises(pavao.config.ConfigException):
			settings.get_setting(*test)

def testCorrect():
	settings = pavao.config.load_settings("configs/correct.yml")
	for test in [
		("pavao.database", databaseSchema),
		("pavao.database.user", str),
		("localization", localizationSchema),
		("giants", giantsSchema),
		("services", servicesSchema)
	]:
		settings.get_setting(*test)

	assert None == settings.get_setting("nonExistent", str)

#-------------------------------------------------------------------------------

if __name__ == "__main__":
	testBadFiles()
	testArrays()
	testVariables()
	testTypes()
	testCorrect()
