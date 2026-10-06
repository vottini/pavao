
import sys
sys.path.append('..')

import warnings
import pytest
from pavao.registry import Registry, EndpointException, insert_sorted, remove_sorted, search_sorted

#-------------------------------------------------------------------------------

class IntValued:
	def __init__(self, value): self.value = value
	def get_value(self): return self.value


def testListSorting():
	contents = [IntValued(x) for x in [ 3, 1, 7, 2, 4, 3, 9, 3 ]]

	listage = list()
	for value in contents:
		insert_sorted(listage, value)

	for idx in range(1, len(listage)):
		assert listage[idx].get_value() > listage[idx-1].get_value()

	for value in contents:
		assert search_sorted(listage, value.get_value()) != None

	not_included = [IntValued(x) for x in [ 5, 0, 6 ]]
	for value in not_included:
		assert search_sorted(listage, value.get_value()) == None

	removed = [IntValued(x) for x in [ 3, 7, 4, 9 ]]
	for value in removed:
		listage = remove_sorted(listage, value.get_value())
		assert search_sorted(listage, value.get_value()) == None

#-------------------------------------------------------------------------------

def testLookup():
	trie = Registry()

	values = {
		"FIRST": ("PUT", "/"),
		"SECOND": ("GET", "/info/public"),
		"THIRD": ("DELETE", "/trash"),
		"FOURTH": ("POST", "/login"),
		"FIFTH": ("GET", "/very/long/path/here")
	}

	for value, endpoint in values.items():
		method, path = endpoint
		trie.add_endpoint(method, path, value)

	for value, endpoint in values.items():
		method, path = endpoint
		retrieved, captured = trie.find_endpoint(method, path)
		assert retrieved == value

	inexistent = (
		("GET", "/reserved/info/public"),
		("POST", "/info/public"),
		("PUT", "/login")
	)

	for method, path in inexistent:
		assert None == trie.find_endpoint(method, path)

#-------------------------------------------------------------------------------

def testDuplications():
	trie = Registry()

	tests = (
		("GET", "/reserved/info/public"),
		("POST", "/info/public"),
		("PUT", "/login")
	)

	for method, endpoint in tests:
		trie.add_endpoint(method, endpoint, "should_work")

	for method, endpoint in tests:
		with pytest.raises(EndpointException):
			trie.add_endpoint(method, endpoint, "should_fail")


def testLength():
	trie = Registry(max_depth=5)
	trie.add_endpoint("GET", "/1/2/3/4/5", "Size Ok")

	with pytest.raises(EndpointException):
		trie.add_endpoint("GET", "/0/1/2/3/4/5/6", "Too long")

	assert None == trie.find_endpoint("GET", "/0/1/2/3/4/5/6")

#-------------------------------------------------------------------------------

def testCapture():
	trie = Registry()
	trie.add_endpoint("POST", "/message/{user}", "FIRST")
	trie.add_endpoint("GET", "/resource/{resource}/status/{status}", "SECOND")

	first_captures = ("john", "doe", "foo", "bar")

	for should_capture in first_captures:
		retrieved, captured = trie.find_endpoint("POST", f"/message/{should_capture}")
		assert retrieved == "FIRST"
		assert captured["user"] == should_capture

	second_captures = (
		("usb", "connected"),
		("keyboard", "caps"),
		("fan", "spinning"),
	)

	for res, status in second_captures:
		retrieved, captured = trie.find_endpoint("GET", f"/resource/{res}/status/{status}")
		assert retrieved == "SECOND"
		assert captured["resource"] == res
		assert captured["status"] == status

	assert None == trie.find_endpoint("POST", "/message")
	assert None == trie.find_endpoint("GET", "/resource/network/status")

#-------------------------------------------------------------------------------

def testTypedCaptures():
	trie = Registry()
	trie.add_endpoint("GET", "/items/{id:int}", "int-endpoint")
	trie.add_endpoint("GET", "/prices/{value:float}", "float-endpoint")

	retrieved, captured = trie.find_endpoint("GET", "/items/42")
	assert retrieved == "int-endpoint"
	assert captured["id"] == 42
	assert isinstance(captured["id"], int)

	retrieved, captured = trie.find_endpoint("GET", "/prices/3.14")
	assert retrieved == "float-endpoint"
	assert captured["value"] == pytest.approx(3.14)
	assert isinstance(captured["value"], float)

	# segment that doesn't satisfy the type constraint → not found
	assert trie.find_endpoint("GET", "/items/notanint") is None
	assert trie.find_endpoint("GET", "/prices/notafloat") is None

def testFallbackCaptureAfterTypeFailure():
	# Bug fix: when {id:int} fails type conversion, routing must fall through
	# to the next capture arc ({name}) rather than returning None immediately
	trie = Registry()
	trie.add_endpoint("GET", "/users/{id:int}", "by-id")
	trie.add_endpoint("GET", "/users/{name}", "by-name")

	# int segment → hits the int arc
	retrieved, captured = trie.find_endpoint("GET", "/users/42")
	assert retrieved == "by-id"
	assert captured["id"] == 42

	# non-int segment → int arc fails, falls through to str arc
	retrieved, captured = trie.find_endpoint("GET", "/users/alice")
	assert retrieved == "by-name"
	assert captured["name"] == "alice"

def testDisallowedBuiltinTypes():
	trie = Registry()

	for dangerous in ("eval", "open", "exec", "compile", "print", "len"):
		with pytest.raises(EndpointException):
			trie.add_endpoint("GET", f"/x/{{id:{dangerous}}}", "endpoint")


def testDuplicateCaptureNameRejected():
	trie = Registry()

	with pytest.raises(EndpointException):
		trie.add_endpoint("GET", "/users/{id}/posts/{id}", "duplicate")

	with pytest.raises(EndpointException):
		trie.add_endpoint("GET", "/a/{x}/b/{x}/c", "duplicate-deep")

	# different names at the same level are fine
	trie.add_endpoint("GET", "/users/{uid}/posts/{pid}", "ok")

def testBinarySearchCorrectness():
	# insert many items in random order and verify sorted retrieval
	import random
	values = list(range(100))
	random.shuffle(values)

	listage = []
	for v in values:
		insert_sorted(listage, IntValued(v))

	keys = [item.get_value() for item in listage]
	assert keys == sorted(keys)
	assert len(keys) == 100

	for v in values:
		assert search_sorted(listage, v) is not None

	for v in values[::3]:
		listage = remove_sorted(listage, v)

	for v in values[::3]:
		assert search_sorted(listage, v) is None

def testRemoveEndpoint():
	trie = Registry()
	trie.add_endpoint("GET", "/users/{id:int}", "users")
	trie.add_endpoint("POST", "/users/{id:int}", "users-post")

	assert trie.find_endpoint("GET", "/users/1") is not None
	trie.remove_endpoint("GET", "/users/{id:int}")
	assert trie.find_endpoint("GET", "/users/1") is None

	# sibling endpoint must survive
	assert trie.find_endpoint("POST", "/users/1") is not None

def testRemoveNonExistentEndpoint():
	# remove_sorted must be a no-op when element is absent
	trie = Registry()
	trie.add_endpoint("GET", "/a", "A")
	trie.remove_endpoint("POST", "/a")       # method not registered
	trie.remove_endpoint("GET", "/missing")  # path not registered
	assert trie.find_endpoint("GET", "/a") is not None

def testRemoveCascadesCleansUpEmptyNodes():
	# removing the only endpoint on a path should prune the now-empty nodes
	trie = Registry()
	trie.add_endpoint("GET", "/deep/nested/path", "only-one")
	trie.remove_endpoint("GET", "/deep/nested/path")

	assert trie.find_endpoint("GET", "/deep/nested/path") is None
	# re-registering the same path must work (nodes were actually pruned)
	trie.add_endpoint("GET", "/deep/nested/path", "re-added")
	retrieved, _ = trie.find_endpoint("GET", "/deep/nested/path")
	assert retrieved == "re-added"

def testRemoveCascadesThroughCaptureArc():
	# exercises the capture-arc branch of the cascade cleanup (line 198)
	trie = Registry()
	trie.add_endpoint("GET", "/users/{id:int}", "users")
	trie.remove_endpoint("GET", "/users/{id:int}")

	assert trie.find_endpoint("GET", "/users/42") is None
	# re-registering must work — capture arc was pruned
	trie.add_endpoint("GET", "/users/{id:int}", "re-added")
	retrieved, captured = trie.find_endpoint("GET", "/users/7")
	assert retrieved == "re-added"
	assert captured["id"] == 7

def testListEndpoints():
	trie = Registry()
	trie.add_endpoint("GET", "/a", "A")
	trie.add_endpoint("POST", "/b", "B")
	trie.add_endpoint("DELETE", "/c", "C")

	endpoints = trie.list_endpoints()
	assert set(endpoints) == {"A", "B", "C"}

#-------------------------------------------------------------------------------

def testRemoveSortedMutatesInPlace():
	listage = [IntValued(x) for x in [1, 3, 5, 7]]
	original = listage
	remove_sorted(listage, 3)
	assert listage is original
	assert [v.get_value() for v in listage] == [1, 5, 7]

def testCapturedDictNotDirtiedOnTypeMismatch():
	# With two capture arcs sharing a suffix, a type failure on the first arc
	# must not leave stale keys in captured from the deeper recursive call.
	trie = Registry()
	trie.add_endpoint("GET", "/a/{id:int}/end", "int-path")
	trie.add_endpoint("GET", "/a/{name}/end", "str-path")

	# "alice" fails int conversion → should fall through to {name}, captured must be clean
	retrieved, captured = trie.find_endpoint("GET", "/a/alice/end")
	assert retrieved == "str-path"
	assert "id" not in captured
	assert captured["name"] == "alice"

def testShadowedUntypedCaptureWarns():
	trie = Registry()
	trie.add_endpoint("GET", "/a/{b}/{c}", "first")
	with pytest.warns(UserWarning, match="'d'.*never match"):
		trie.add_endpoint("GET", "/a/{b}/{d}", "second")

def testShadowedTypedCaptureSameTypeWarns():
	trie = Registry()
	trie.add_endpoint("GET", "/items/{id:int}", "first")
	with pytest.warns(UserWarning, match="'count'.*never match"):
		trie.add_endpoint("GET", "/items/{count:int}", "second")

def testDifferentTypedCapturesNoWarning():
	# int and float at the same position are not shadows — they match different inputs
	trie = Registry()
	trie.add_endpoint("GET", "/v/{id:int}", "int-endpoint")
	with warnings.catch_warnings():
		warnings.simplefilter("error")
		trie.add_endpoint("GET", "/v/{price:float}", "float-endpoint")

def testTypedPlusUntypedNoWarning():
	# typed + untyped fallthrough is the intended use case — must not warn
	trie = Registry()
	trie.add_endpoint("GET", "/users/{id:int}", "by-id")
	with warnings.catch_warnings():
		warnings.simplefilter("error")
		trie.add_endpoint("GET", "/users/{name}", "by-name")

#-------------------------------------------------------------------------------

if __name__ == "__main__":
	testListSorting()
	testLookup()
	testDuplications()
	testLength()
	testCapture()
	testTypedCaptures()
	testFallbackCaptureAfterTypeFailure()
	testDisallowedBuiltinTypes()
	testRemoveEndpoint()
	testListEndpoints()
