
import sys
sys.path.append('..')

import pytest
import pavao

def testListSorting():
	contents = [ 3, 1, 7, 2, 4, 3, 9, 3 ]

	listage = list()
	for value in contents:
		pavao.http.insert_sorted(listage, value)

	for idx in range(1, len(listage)):
		assert listage[idx] > listage[idx-1]
	
	for value in contents:
		assert pavao.http.search_sorted(listage, value) != None

	not_included = [ 5, 0, 6 ]
	for value in not_included:
		assert pavao.http.search_sorted(listage, value) == None

#-------------------------------------------------------------------------------

def testLookup():
	trie = pavao.http.Registry()

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
	trie = pavao.http.Registry()

	tests = (
		("GET", "/reserved/info/public"),
		("POST", "/info/public"),
		("PUT", "/login")
	)

	for method, endpoint in tests:
		trie.add_endpoint(method, endpoint, "should_work")

	for method, endpoint in tests:
		with pytest.raises(pavao.http.EndpointException):
			trie.add_endpoint(method, endpoint, "should_fail")


def testLength():
	trie = pavao.http.Registry(max_depth=5)
	trie.add_endpoint("GET", "/1/2/3/4/5", "Size Ok")

	with pytest.raises(pavao.http.EndpointException):
		trie.add_endpoint("GET", "/0/1/2/3/4/5/6", "Too long")

	assert None == trie.find_endpoint("GET", "/0/1/2/3/4/5/6")

#-------------------------------------------------------------------------------

def testCapture():
	trie = pavao.http.Registry()
	trie.add_endpoint("POST", "/message/{user}", "FIRST")
	trie.add_endpoint("GET", "/resource/{resource}/status/{status}", "SECOND")

	first_captures = (
		"john",
		"doe",
		"foo",
		"bar"
	)

	for should_capture in first_captures:
		retrieved, captured = trie.find_endpoint(
			"POST", f"/message/{should_capture}")

		assert (retrieved == "FIRST"
			and captured["user"] == should_capture)

	second_captures = (
		("usb", "connected"),
		("keyboard", "caps"),
		("fan", "spinning"),
	)

	for res, status in second_captures:
		retrieved, captured = trie.find_endpoint(
			"GET", f"/resource/{res}/status/{status}")

		assert (retrieved == "SECOND"
			and captured["resource"] == res
			and captured["status"] == status)

	assert None == trie.find_endpoint("POST", "/message")
	assert None == trie.find_endpoint("GET", "/resource/network/status")


#-------------------------------------------------------------------------------

if __name__ == "__main__":
	testListSorting()
	testLookup()
	testDuplications()
	testLength()
	testCapture()

