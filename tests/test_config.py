
import sys
sys.path.append('..')

import pytest
import pavao


def testBadFiles():

	badFiles = [
		"configs/non_existent_file.yml",
		"configs/bad_file.yml"
	]

	for badFile in badFiles:
		with pytest.raises(pavao.config.ConfigException):
			pavao.config.loadSettings(badFile)

#-------------------------------------------------------------------------------

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

giantsSchema = [
	str
]

servicesSchema = [{
	"name": str,
	"url": str,
	"prefix": "/api"
}]

positionSchema = {
	"latitude": float,
	"longitude": float,
	"accuracy": 10.0
}

#-------------------------------------------------------------------------------

def testMissing():

	missingFiles = [
		"missing_type.yml",
		"missing_dict.yml",
	]

	for file in missingFiles:
		with pytest.raises(pavao.config.ConfigException):
			settings = pavao.config.loadSettings("configs/" + file)
			settings.getSetting("pavao.database", databaseSchema)


def testArrays():
	settings = pavao.config.loadSettings("configs/array_incompat.yml")

	tests = [
		("localization", localizationSchema),
		("giants", giantsSchema)
	]

	for test in tests:
		with pytest.raises(pavao.config.ConfigException):
			settings.getSetting(*test)

	badGiantsSchemas = [
		[ str, int ],
		[ (str, int) ]
	]

	settings = pavao.config.loadSettings("configs/correct.yml")
	for badGiantsSchema in badGiantsSchemas:
		with pytest.raises(pavao.config.ConfigException):
			settings.getSetting("giants", badGiantsSchema)


def testVariables():
	settings = pavao.config.loadSettings("configs/missing_var.yml")

	tests = [
		("pavao.database", databaseSchema),
		("position", positionSchema),
	]

	for test in tests:
		with pytest.raises(pavao.config.ConfigException):
			settings.getSetting(*test)


def testTypes():
	settings = pavao.config.loadSettings("configs/bad_types.yml")

	tests = [
		("position1", positionSchema),
		("position2", positionSchema)
	]

	for test in tests:
		with pytest.raises(pavao.config.ConfigException):
			settings.getSetting(*test)


def testCorrect():
	settings = pavao.config.loadSettings("configs/correct.yml")

	tests = [
		("pavao.database", databaseSchema),
		("pavao.database.user", str),
		("localization", localizationSchema), 
		("giants", giantsSchema),
		("services", servicesSchema)
	]

	for test in tests:
		settings.getSetting(*test)

	assert None == settings.getSetting("nonExistent", str)

#-------------------------------------------------------------------------------

if __name__ == "__main__":
	testBadFiles()
	testArrays()
	testVariables()
	testTypes()
	testCorrect()

