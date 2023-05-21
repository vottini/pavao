
import re
_capture_pattern = re.compile(r'^{([a-zA-Z_][a-zA-Z_0-9]*)}$')

#-------------------------------------------------------------------------------

def insert_sorted(listage, elem, selector = lambda x : x):
	elem_key = selector(elem)
	max_index = len(listage)
	list_value = None

	index = 0
	while index < max_index:
		list_value = selector(listage[index])
		if not list_value < elem_key:
			break

		index += 1

	if list_value == elem_key:
		print("Same value added twice")
		return False

	if index == max_index:
		listage.append(elem)
		return True

	listage.insert(index, elem)
	return True


def search_sorted(listage, query, selector = lambda x : x):
	max_index = len(listage)
	list_value = None

	index = 0
	while index < max_index:
		list_value = selector(listage[index])
		if not list_value < query:
			break

		index += 1

	if index < max_index and list_value == query:
		return listage[index]

	return None

#-------------------------------------------------------------------------------

_path_selector = lambda node: node.token
_not_empty = lambda x: len(x) > 0

class EndpointNode:
	def __init__(self, parent, token):
		self.parent = parent
		self.token = token

		self.raw_children = list()
		self.capture_children = list()
		self.endpoints = dict()


	def add_leaf(self, method, url_tokens, handler):

		if len(url_tokens) == 0:
			if method in self.endpoints:
				print("ENTRYPOINT ALREADY REGISTERED")
				return False

			self.endpoints[method] = handler
			return True

		destination_children = self.raw_children
		current_token, *remaining_tokens = url_tokens
		capture_match = _capture_pattern.search(current_token)

		if None != capture_match:
			current_token = capture_match.group(1)
			destination_children = self.capture_children

		existing_node = search_sorted(
			destination_children, current_token,
			_path_selector)

		if None != existing_node:
			return existing_node.add_leaf(method, remaining_tokens,
				handler)

		new_node = EndpointNode(self, current_token)
		if new_node.add_leaf(method, remaining_tokens, handler):
			insert_sorted(destination_children, new_node, _path_selector)
			return True

		return False


	def lookup_endpoint(self, method, url_tokens, captured):

		if len(url_tokens) == 0:
				return self.endpoints.get(method)

		current_token, *remaining_tokens = url_tokens
		raw_node = search_sorted(self.raw_children, current_token,
			_path_selector)

		if None != raw_node:
			return raw_node.lookup_endpoint(method,
				remaining_tokens, captured)

		for capture_child in self.capture_children:
			found = capture_child.lookup_endpoint(method,
				remaining_tokens, captured)

			if None != found:
				captured_token = capture_child.token
				captured[captured_token] = current_token
				return found

		return None


class EndpointTrie:
	def __init__(self, max_depth=10):
		self.root = EndpointNode(None, '/')
		self.max_depth = max_depth


	def add_endpoint(self, method, path, handler):
		raw_tokens = path.strip("/").split("/")
		valid_tokens = tuple(filter(_not_empty, raw_tokens))
		if len(valid_tokens) > self.max_depth:
			print("ERROO!!"); return

		self.root.add_leaf(
			method,
			valid_tokens,
			handler
		)


	def find_endpoint(self, method, url):
		raw_tokens = url.strip("/").split("/")
		valid_tokens = tuple(filter(_not_empty, raw_tokens))
		captured = dict()

		result = self.root.lookup_endpoint(method, valid_tokens, captured)
		return (result, captured) if None != result else None

#-------------------------------------------------------------------------------

#a = list()
#_insert_sorted(a, 3)
#_insert_sorted(a, 1)
#_insert_sorted(a, 7)
#_insert_sorted(a, 2)
#_insert_sorted(a, 4)
#_insert_sorted(a, 3)
#_insert_sorted(a, 9)
#
#print(a)
#print(_search_sorted(a, 3))
#print(_search_sorted(a, 4))
#print(_search_sorted(a, 5))
#print(_search_sorted(a, 9))

trie = EndpointTrie()
trie.add_endpoint("PUT", "/", "lala0")
trie.add_endpoint("GET", "/info/public", "lala1")
trie.add_endpoint("DELETE", "/trash", "lala2")
trie.add_endpoint("POST", "/login", "lala3")
trie.add_endpoint("POST", "/message/{user}", "lala5")
trie.add_endpoint("GET", "/resource/{resource}/status/{status}", "lala6")

print(trie.find_endpoint("PUT", "/"))
print(trie.find_endpoint("GET", "/info/public"))
print(trie.find_endpoint("DELETE", "/trash"))
print(trie.find_endpoint("POST", "/login"))
print(trie.find_endpoint("POST", "/message/gustavo"))
print(trie.find_endpoint("GET", "/resource/usb/status/on"))

print(trie.find_endpoint("GET", "/reserved/info/public"))
print(trie.find_endpoint("POST", "/info/public"))
print(trie.find_endpoint("GET", "/data/alloc"))
print(trie.find_endpoint("POST", "/message"))
print(trie.find_endpoint("GET", "/resource/network/status"))

__all__ = [
	"insert_sorted",
	"search_sorted",
	"EndpointTrie"
]

