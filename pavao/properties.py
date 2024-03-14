
import os
import configparser

_dummy_header = "sectionless"
def section_injector(file_descriptor):
	yield f"[{_dummy_header}]\n"
	yield from file_descriptor


def load_properties(file_path):
	parser = configparser.ConfigParser()
	parser.read_file(section_injector(open(file_path)),
		os.path.basename(file_path))

	properties = dict()
	for prop in parser.options(_dummy_header):
		properties[prop] = parser[_dummy_header][prop]

	return properties


__all__ = [
	"load_properties"
]
