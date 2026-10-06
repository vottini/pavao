
import re
import bisect
import warnings

_identifier = r'[a-zA-Z_][a-zA-Z_0-9]*'
_capture_pattern = re.compile(fr'^{{({_identifier})(?::({_identifier}))?}}$')
_identity = lambda x : x
_allowed_types = {'int': int, 'float': float, 'str': str}

from .exception import PavaoException
class EndpointException(PavaoException):
	pass

#-------------------------------------------------------------------------------

_arc_key = lambda arc: arc.get_value()

def insert_sorted(listage, valued):
	elem_key = valued.get_value()
	index = bisect.bisect_left(listage, elem_key, key=_arc_key)
	if index < len(listage) and listage[index].get_value() == elem_key:
		return False
	listage.insert(index, valued)
	return True


def remove_sorted(listage, query_string):
	index = bisect.bisect_left(listage, query_string, key=_arc_key)
	if index < len(listage) and listage[index].get_value() == query_string:
		del listage[index]
	return listage


def search_sorted(listage, query_string):
	index = bisect.bisect_left(listage, query_string, key=_arc_key)
	if index < len(listage) and listage[index].get_value() == query_string:
		return listage[index]
	return None

#-------------------------------------------------------------------------------

class RawArc:
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

def _warn_if_shadowed(new_arc, capture_children):
	for arc in capture_children:
		if arc.transform is _identity and new_arc.transform is _identity:
			warnings.warn(
				f"Capture variable '{new_arc.get_value()}' will never match: "
				f"untyped capture '{arc.get_value()}' at the same path position always takes priority.",
				stacklevel=5
			)
			return
		if arc.transform is new_arc.transform and arc.transform is not _identity:
			warnings.warn(
				f"Capture variable '{new_arc.get_value()}' will never match: "
				f"typed capture '{arc.get_value()}' with the same type at the same path position always takes priority.",
				stacklevel=5
			)
			return

#-------------------------------------------------------------------------------

class RegistryNode:
	def __init__(self):
		self.raw_children = list()
		self.capture_children = list()
		self.endpoints = dict()

	def is_empty(self):
		children_size = len(self.raw_children) + len(self.capture_children)
		return (children_size + len(self.endpoints)) == 0


	def list_endpoints(self):
		result = [ specs for specs in self.endpoints.values() ]
		for arc in self.raw_children: result += arc.node.list_endpoints()
		for arc in self.capture_children: result += arc.node.list_endpoints()
		return result


	def add_leaf(self, method, url_tokens, endpoint_data, verify_existence=True, seen_captures=None):

		if len(url_tokens) == 0:
			if verify_existence and method in self.endpoints:
				msg = "Endpoint already registered"
				raise EndpointException(msg)

			self.endpoints[method] = endpoint_data
			return

		if seen_captures is None:
			seen_captures = frozenset()

		current_token, *remaining_tokens = url_tokens
		destination_children = self.raw_children
		new_arc = RawArc(current_token)

		if (capture_match := _capture_pattern.search(current_token)) is not None:
			current_token = capture_match.group(1)
			transform = _identity

			if current_token in seen_captures:
				msg = f"Duplicate capture variable '{current_token}' in path"
				raise EndpointException(msg)

			seen_captures = seen_captures | {current_token}

			if (specified_type := capture_match.group(2)) is not None:
				transform = _allowed_types.get(specified_type)

				if transform is None:
					msg = f"Unknown type '{specified_type}'"
					raise EndpointException(msg)

			destination_children = self.capture_children
			new_arc = CaptureArc(current_token, transform)

		existing_arc = search_sorted(
			destination_children,
			current_token)

		if existing_arc is not None:
			existing_node = existing_arc.node
			return existing_node.add_leaf(method,
				remaining_tokens, endpoint_data,
				verify_existence, seen_captures)

		if isinstance(new_arc, CaptureArc):
			_warn_if_shadowed(new_arc, self.capture_children)

		new_node = RegistryNode()
		new_node.add_leaf(method, remaining_tokens,
			endpoint_data, verify_existence, seen_captures)

		new_arc.set_node(new_node)
		insert_sorted(destination_children, new_arc)


	def remove_endpoint(self, method, url_tokens):

		if len(url_tokens) == 0:
			popped = self.endpoints.pop(method, None)
			return popped is not None and self.is_empty()

		current_token, *remaining_tokens = url_tokens
		source_children = self.raw_children
		is_capture = False

		if (capture_match := _capture_pattern.search(current_token)) is not None:
			current_token = capture_match.group(1)
			source_children = self.capture_children
			is_capture = True

		found_arc = search_sorted(source_children, current_token)

		if found_arc is not None:
			node = found_arc.node
			has_empty_child = node.remove_endpoint(method, remaining_tokens)

			if has_empty_child:
				remove_sorted(source_children, current_token)
				if self.is_empty():
					return True

		return False


	def lookup_endpoint(self, method, url_tokens, captured):

		if len(url_tokens) == 0:
			return self.endpoints.get(method)

		current_token, *remaining_tokens = url_tokens
		raw_arc = search_sorted(self.raw_children,
			current_token)

		if raw_arc is not None:
			node = raw_arc.node
			return node.lookup_endpoint(method,
				remaining_tokens, captured)

		for capture_arc in self.capture_children:
			try:
				probe_value = capture_arc.assume(current_token)
			except Exception:
				continue

			found = capture_arc.node.lookup_endpoint(method, remaining_tokens, captured)
			if found is not None:
				captured[capture_arc.get_value()] = probe_value
				return found

		return None

#-------------------------------------------------------------------------------

class Registry:
	def __init__(self, max_depth=10):
		self.root = RegistryNode()
		self.max_depth = max_depth


	def add_endpoint(self, method, path, endpoint_data):
		raw_tokens = path.strip("/").split("/")
		valid_tokens = tuple(filter(bool, raw_tokens))

		if len(valid_tokens) > self.max_depth:
			msg = "Given endpoint requires depth greater than allowed"
			raise EndpointException(msg)

		self.root.add_leaf(
			method,
			valid_tokens,
			endpoint_data
		)


	def remove_endpoint(self, method, url):
		raw_tokens = url.strip("/").split("/")
		valid_tokens = tuple(filter(bool, raw_tokens))
		self.root.remove_endpoint(method, valid_tokens)


	def find_endpoint(self, method, url):
		raw_tokens = url.strip("/").split("/")
		valid_tokens = tuple(filter(bool, raw_tokens))
		if len(valid_tokens) > self.max_depth:
			return None

		captured = dict()
		result = self.root.lookup_endpoint(method, valid_tokens, captured)
		return (result, captured) if result is not None else None


	def list_endpoints(self):
		return self.root.list_endpoints()

#-------------------------------------------------------------------------------

__all__ = [
	"EndpointException",
	"insert_sorted",
	"remove_sorted",
	"search_sorted",
	"Registry"
]

