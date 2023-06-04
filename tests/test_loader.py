
import sys
sys.path.append('..')

import pytest
import pavao

def testLoading():

	answers = {
		'loading/world.py': 'World',
		'loading/hello_world.py': 'Hello World!... whatever',
		'loading/hello.py': 'Hello',
		'loading/submodule1/something.py': 'something',
		'loading/submodule1/submodule11/whenever.py': 'whenever... Hello',
		'loading/submodule1/submodule11/whatever.py': 'whatever',
		'loading/submodule2/anything.py': 'anything',
	}

	loaded = pavao.load_dir('loading')
	for file_path, file_hash, fnc in loaded:
		expected = answers.get(file_path)
		assert expected == fnc()


def testUnloadable():

	with_problems = [
		'loading/missing.py'
		'loading/submodule1/something.py'
		'loading/submodule2/nothing.py'
	]

	loaded = pavao.load_dir('loading')
	for bad_file in with_problems:
		for loaded_path, *_ in loaded:
			assert bad_file != loaded_path


def testBadPath():
	loaded = pavao.load_dir('inexisttent')
	assert 0 == len(loaded)

#-------------------------------------------------------------------------------

if __name__ == "__main__":
	testLoading()
	testUnloadable()
	testBadPath()

