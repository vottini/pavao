
import re
import builtins

_identifier = r'[a-zA-Z_][a-zA-Z_0-9]*'
_capture_pattern = re.compile(fr'^{{({_identifier})(?::({_identifier}))?}}$')
_not_empty = lambda x: len(x) > 0
_identity = lambda x : x

from ..exception import PavaoException
class EndpointException(PavaoException):
	pass

#-------------------------------------------------------------------------------

class Valued:
	def get_value(self):
		pass


def insert_sorted(listage, valued):
	elem_key = valued.get_value()
	max_index = len(listage)
	list_value = None

	index = 0
	while index < max_index:
		list_value = listage[index].get_value()
		if not list_value < elem_key:
			break

		index += 1

	if list_value == elem_key:
		return False

	if index == max_index:
		listage.append(valued)
		return True

	listage.insert(index, valued)
	return True


def search_sorted(listage, query_string):
	max_index = len(listage)
	list_value = None

	index = 0
	while index < max_index:
		list_value = listage[index].get_value()
		if not list_value < query_string:
			break

		index += 1

	if index < max_index and list_value == query_string:
		return listage[index]

	return None

#-------------------------------------------------------------------------------

class RawArc(Valued):
	def __init__(self, label):
		self.label = label
		self.node = None

	def get_value(self): return self.label
	def set_node(self, node): self.node = node


class CaptureArc(RawArc):
	def __init__(self, label, transform):
		super().__init__(label)
		self.transform = transform

	def assume(self, value):
		return self.transform(value)

#-------------------------------------------------------------------------------

class EndpointNode:
	def __init__(self, parent):
		self.parent = parent
		self.raw_children = list()
		self.capture_children = list()
		self.endpoints = dict()


	def add_leaf(self, method, url_tokens, handler):

		if len(url_tokens) == 0:
			if method in self.endpoints:
				msg = "Endpoint already registered"
				raise EndpointException(msg)

			self.endpoints[method] = handler
			return

		current_token, *remaining_tokens = url_tokens
		destination_children = self.raw_children
		new_arc = RawArc(current_token)

		if 	(capture_match := _capture_pattern.search(current_token)) is not None:
			current_token = capture_match.group(1)
			transform = _identity

			if (specified_type := capture_match.group(2)) is not None:
				transform = getattr(builtins, specified_type, None)

				if transform is None:
					msg = f"Unknown type: {specified_type}"
					raise EndpointException(msg)

			destination_children = self.capture_children
			new_arc = CaptureArc(current_token, transform)

		existing_arc = search_sorted(
			destination_children,
			current_token)

		if None != existing_arc:
			existing_node = existing_arc.node
			return existing_node.add_leaf(method, remaining_tokens,
				handler)

		new_node = EndpointNode(self)
		new_node.add_leaf(method, remaining_tokens, handler)
		insert_sorted(destination_children, new_arc)
		new_arc.set_node(new_node)


	def lookup_endpoint(self, method, url_tokens, captured):

		if len(url_tokens) == 0:
			return self.endpoints.get(method)

		current_token, *remaining_tokens = url_tokens
		raw_arc = search_sorted(self.raw_children,
			current_token)

		if None != raw_arc:
			node = raw_arc.node
			return node.lookup_endpoint(method,
				remaining_tokens, captured)

		for capture_arc in self.capture_children:
			node = capture_arc.node
			found = node.lookup_endpoint(method,
				remaining_tokens, captured)

			if None != found:
				try: probe_value = capture_arc.assume(current_token)
				except Exception as e:
					return None

				label = capture_arc.get_value()
				captured[label] = probe_value
				return found

		return None


class Registry:
	def __init__(self, max_depth=10):
		self.root = EndpointNode(None)
		self.max_depth = max_depth


	def add_endpoint(self, method, path, handler):
		raw_tokens = path.strip("/").split("/")
		valid_tokens = tuple(filter(_not_empty, raw_tokens))

		if len(valid_tokens) > self.max_depth:
			msg = "Given endpoint requires depth greater than allowed"
			raise EndpointException(msg)

		self.root.add_leaf(
			method,
			valid_tokens,
			handler
		)


	def find_endpoint(self, method, url):
		raw_tokens = url.strip("/").split("/")
		valid_tokens = tuple(filter(_not_empty, raw_tokens))
		if len(valid_tokens) > self.max_depth:
			return None

		captured = dict()
		result = self.root.lookup_endpoint(method, valid_tokens, captured)
		return (result, captured) if None != result else None

#-------------------------------------------------------------------------------

__all__ = [
	"EndpointException",
	"insert_sorted",
	"search_sorted",
	"Registry"
]

