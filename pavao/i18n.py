
import os
import glob
import configparser
from datetime import datetime, timezone

from .logger import Logger
from .utils import error_blueprint

_dummy_header = "messages"

# inspired by
# https://stackoverflow.com/a/2819788/21680913
# (warownia1's comment)

def section_injector(file_descriptor):
	yield f"[{_dummy_header}]\n"
	yield from file_descriptor


def _clean(msg):
	return msg.strip('"')

#-------------------------------------------------------------------------------

class Localizer:
	def __init__(self, sources):
		self.sources = sources


	def get_message(self, messageId):
		sanedId = messageId.lower()
		for source in self.sources:
			msg = source.get(sanedId)

			if msg is not None:
				return _clean(msg)

		Logger.warning(f"Message id '{messageId}' not found")
		return "<Unknown>"


	def create_error(self, messageId):
		desc = self.get_message(messageId)

		return {
			"error": messageId,
			"description": desc,
			"timestamp": datetime.now(timezone.utc)
		}


	def assign_response_error(self, response, messageId):
		payload = self.create_error(messageId)
		serialized = error_blueprint.serialize(payload)
		response.set_content('application/json', serialized.encode())


class Internationalization:
	def __init__(self, i18n_dir, fallback_language='en_US'):
		ini_files = glob.glob(os.path.join(i18n_dir, '*.ini'))

		self.fallback = dict()
		self.languages = dict()

		for fullpath in ini_files:
			filename = os.path.basename(fullpath)
			language = filename.split('.')[0]
			config = configparser.ConfigParser()

			with open(fullpath) as f:
				config.read_file(section_injector(f))

			messages = dict()
			for message in config.options(_dummy_header):
				messages[message] = config[_dummy_header][message]

			self.languages[language] = messages
			if language == fallback_language:
				self.fallback = messages


	def localize(self, languageId, messageId):
		sanedId = messageId.lower()

		if languageId in self.languages:
			msg = self.languages[languageId].get(sanedId)
			if msg is not None:
				return _clean(msg)

		for existing_language in self.languages.keys():
			if existing_language.startswith(languageId):
				msg = self.languages[existing_language].get(sanedId)
				if msg is not None:
					return _clean(msg)

		msg = self.fallback.get(sanedId)
		if msg is not None:
			return _clean(msg)

		Logger.warning(f"Message id '{messageId}' not found")
		return "<Unknown>"


	def create_localizer(self, localization_priority):
		if len(localization_priority) == 0:
			return Localizer([self.fallback])

		sources = list()
		for languageId in localization_priority:
			if languageId in self.languages:
				sources.append(self.languages[languageId])
			elif '_' in languageId:
				base = languageId.split('_')[0]
				if base in self.languages:
					sources.append(self.languages[base])

		if self.fallback not in sources:
			sources.append(self.fallback)

		return Localizer(sources)

#-------------------------------------------------------------------------------

class LazyLocalizer:
	def __init__(self, localizer, module, fragment):
		self.localizer = localizer
		self.module = module
		self.fragment = fragment


	def identity(self):
		return f"{self.module}::{self.fragment}"


	def localize(self, localization_priority):
		translator = self.localizer.create_localizer(localization_priority)
		return translator.get_message(self.fragment)


class ModuleLocalizer:
	def __init__(self, module, i18n_dir):
		self.localizer = Internationalization(i18n_dir)
		self.module = module


	def map(self, fragment):
		return LazyLocalizer(
			self.localizer,
			self.module,
			fragment)


__all__ = [
	"Internationalization",
	"ModuleLocalizer",
	"LazyLocalizer"
]
