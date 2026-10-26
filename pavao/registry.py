
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
		self.origin = None

	def assume(self, value):
		return self.transform(value)

#-------------------------------------------------------------------------------

class RegistryNode:
	def __init__(self):
		self.raw_children = list()
		self.capture_children = list()
		self.endpoint = None

	def is_empty(self):
		children_size = len(self.raw_children) + len(self.capture_children)
		return children_size == 0 and self.endpoint is None


	def list_endpoints(self):
		result = [self.endpoint] if self.endpoint is not None else []
		for arc in self.raw_children: result += arc.node.list_endpoints()
		for arc in self.capture_children: result += arc.node.list_endpoints()
		return result


	def has_template_path(self, url_tokens):
		"""Check whether this subtree contains an endpoint at the given template path."""
		if len(url_tokens) == 0:
			return self.endpoint is not None

		current_token, *remaining_tokens = url_tokens

		if (m := _capture_pattern.search(current_token)) is not None:
			arc = search_sorted(self.capture_children, m.group(1))
		else:
			arc = search_sorted(self.raw_children, current_token)

		return arc is not None and arc.node.has_template_path(remaining_tokens)


	def find_shadow(self, url_tokens):
		"""
		Walk url_tokens through the existing trie. At each capture position,
		if a new arc would be created AND an existing arc of the same type already
		covers the full remaining path, return (new_var_name, transform, shadowing_arc).
		Returns None when no shadow is found.
		"""
		if len(url_tokens) == 0:
			return None

		current_token, *remaining_tokens = url_tokens

		if (m := _capture_pattern.search(current_token)) is not None:
			name = m.group(1)
			specified_type = m.group(2)
			transform = _allowed_types.get(specified_type, _identity) if specified_type else _identity

			existing = search_sorted(self.capture_children, name)
			if existing is not None:
				# Arc reused — no shadow at this level, recurse
				return existing.node.find_shadow(remaining_tokens)

			# New arc — check if any existing arc shadows the full remaining path
			for arc in self.capture_children:
				both_untyped = arc.transform is _identity and transform is _identity
				same_typed = arc.transform is transform and transform is not _identity
				if (both_untyped or same_typed) and arc.node.has_template_path(remaining_tokens):
					return (name, transform, arc)

			# New arc is not shadowed; its subtree is empty so nothing deeper can be either
			return None

		else:
			arc = search_sorted(self.raw_children, current_token)
			if arc is None:
				return None
			return arc.node.find_shadow(remaining_tokens)


	def add_leaf(self, url_tokens, endpoint_data, verify_existence=True, seen_captures=None, method=None, full_path=None):

		if len(url_tokens) == 0:
			if verify_existence and self.endpoint is not None:
				msg = "Endpoint already registered"
				raise EndpointException(msg)

			self.endpoint = endpoint_data
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
			return existing_arc.node.add_leaf(remaining_tokens, endpoint_data,
				verify_existence, seen_captures, method, full_path)

		if isinstance(new_arc, CaptureArc):
			new_arc.origin = f"{method} {full_path}" if method and full_path else full_path

		new_node = RegistryNode()
		new_node.add_leaf(remaining_tokens, endpoint_data,
			verify_existence, seen_captures, method, full_path)

		new_arc.set_node(new_node)
		insert_sorted(destination_children, new_arc)


	def remove_endpoint(self, url_tokens):

		if len(url_tokens) == 0:
			had = self.endpoint is not None
			self.endpoint = None
			return had and self.is_empty()

		current_token, *remaining_tokens = url_tokens
		source_children = self.raw_children

		if (capture_match := _capture_pattern.search(current_token)) is not None:
			current_token = capture_match.group(1)
			source_children = self.capture_children

		found_arc = search_sorted(source_children, current_token)

		if found_arc is not None:
			has_empty_child = found_arc.node.remove_endpoint(remaining_tokens)

			if has_empty_child:
				remove_sorted(source_children, current_token)
				if self.is_empty():
					return True

		return False


	def lookup_endpoint(self, url_tokens, captured):

		if len(url_tokens) == 0:
			return self.endpoint

		current_token, *remaining_tokens = url_tokens
		raw_arc = search_sorted(self.raw_children, current_token)

		if raw_arc is not None:
			return raw_arc.node.lookup_endpoint(remaining_tokens, captured)

		for capture_arc in self.capture_children:
			try:
				probe_value = capture_arc.assume(current_token)
			except Exception:
				continue

			found = capture_arc.node.lookup_endpoint(remaining_tokens, captured)
			if found is not None:
				captured[capture_arc.get_value()] = probe_value
				return found

		return None

#-------------------------------------------------------------------------------

class Registry:
	def __init__(self, max_depth=10):
		self.roots = {}
		self.max_depth = max_depth


	def add_endpoint(self, method, path, endpoint_data):
		raw_tokens = path.strip("/").split("/")
		valid_tokens = tuple(filter(bool, raw_tokens))

		if len(valid_tokens) > self.max_depth:
			msg = "Given endpoint requires depth greater than allowed"
			raise EndpointException(msg)

		root = self.roots.setdefault(method, RegistryNode())

		shadow = root.find_shadow(valid_tokens)
		if shadow is not None:
			new_var, transform, arc = shadow
			endpoint_info = f" (endpoint: {method} {path})"
			conflict_info = f" (conflicts with: {arc.origin})" if arc.origin else ""
			if transform is _identity:
				msg = (f"Capture variable '{new_var}' will never match: "
					f"untyped capture '{arc.get_value()}' at the same path position always takes priority."
					f"{endpoint_info}{conflict_info}")
			else:
				msg = (f"Capture variable '{new_var}' will never match: "
					f"typed capture '{arc.get_value()}' with the same type at the same path position always takes priority."
					f"{endpoint_info}{conflict_info}")
			warnings.warn(msg, stacklevel=3)

		root.add_leaf(valid_tokens, endpoint_data, method=method, full_path=path)


	def remove_endpoint(self, method, url):
		raw_tokens = url.strip("/").split("/")
		valid_tokens = tuple(filter(bool, raw_tokens))
		if method in self.roots:
			self.roots[method].remove_endpoint(valid_tokens)


	def find_endpoint(self, method, url):
		raw_tokens = url.strip("/").split("/")
		valid_tokens = tuple(filter(bool, raw_tokens))
		if len(valid_tokens) > self.max_depth:
			return None

		root = self.roots.get(method)
		if root is None:
			return None

		captured = dict()
		result = root.lookup_endpoint(valid_tokens, captured)
		return (result, captured) if result is not None else None


	def list_endpoints(self):
		result = []
		for root in self.roots.values():
			result += root.list_endpoints()
		return result

#-------------------------------------------------------------------------------

__all__ = [
	"EndpointException",
	"insert_sorted",
	"remove_sorted",
	"search_sorted",
	"Registry"
]
