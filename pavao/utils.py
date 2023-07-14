
import sys
import inspect
import configparser
import os
import re

from .exception import PavaoException
from .logger import Logger

_quality_matcher = re.compile(r'^q=(1|0.[0-9]{1,3})$')
_any_language = '*'

#-------------------------------------------------------------------------------

def include(filename):
	callerFrame = inspect.stack()[1]
	callerPath = os.path.abspath(callerFrame.filename)
	callerDir = os.path.dirname(callerPath)

	filePath = os.path.join(callerDir, filename)
	with open(filePath) as fd:
		return fd.read()

#-------------------------------------------------------------------------------

class Localization:
	def __init__(self, content, fallback_language='en'):
		self.fallback = dict()

		config = configparser.ConfigParser()
		config.read_string(content)

		self.languages = dict()
		for language in config.sections():
			messages = dict()

			for message in config.options(language):
				value = config[language][message]
				messages[message] = value

			self.languages[language] = messages
			if language == fallback_language:
				self.fallback = messages


	class Localizer:
		def __init__(self, sources):
			self.sources = sources

		def get_message(self, messageId):
			sanedId = messageId.lower()

			for source in self.sources:
				msg = source.get(sanedId)
				if msg is not None:
					return msg

			Logger.warning(f"Message id '{messageId}' not found")
			return "<Unknown message>"


	# see more on
	# https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Accept-Language
	# https://developer.mozilla.org/en-US/docs/Glossary/Quality_values

	def create_localizer(self, request):
		acceptedLanguages = request.headers.get('accept-language')

		if acceptedLanguages is None:
			sources = [ self.fallback ]
			return Localization.Localizer(sources)

		parsedLanguages = list()
		for languageSpec in acceptedLanguages:
			parts = languageSpec.split(';', maxsplit=1)

			languageId = parts[0].strip()
			if _any_language == languageId:
				continue

			quality = 1.0
			if len(parts) > 1:
				quality_part = parts[1]
				found = _quality_matcher.match(quality_part)

				if None != found:
					quality_str = found.group(1)
					quality = float(quality_str)
				
			parsedLanguages.append((languageId, quality))

		parsedLanguages.sort(key=lambda x : x[1], reverse=True)

		sources = list()
		for languageId, _ in parsedLanguages:
			if languageId in self.languages:
				sources.append(self.languages[languageId])

		sources.append(self.fallback)
		return Localization.Localizer(sources)


	def localize(self, languageId, messageId):
		sources = list()
		if languageId in self.languages:
			sources.append(self.languages[languageId])

		sources.append(self.fallback)
		for source in self.sources:
			msg = source.get(sanedId)
			if msg is not None:
				return msg

		Logger.warning(f"Message id '{messageId}' not found")
		return "<Unknown message>"

#-------------------------------------------------------------------------------

__all__ = [
	"include",
	"Localization"
]

