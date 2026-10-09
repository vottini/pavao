
import sys
sys.path.append('..')

import pytest
from datetime import timezone
from unittest.mock import MagicMock, patch

from pavao.i18n import (
	section_injector, _clean,
	Localizer, Internationalization,
	LazyLocalizer, ModuleLocalizer
)

#-------------------------------------------------------------------------------
# helpers

def make_i18n_dir(tmp_path, languages):
	for lang, messages in languages.items():
		content = '\n'.join(f'{k} = {v}' for k, v in messages.items())
		(tmp_path / f'{lang}.ini').write_text(content)
	return str(tmp_path)

#-------------------------------------------------------------------------------
# section_injector

def testSectionInjectorYieldsDummyHeaderFirst():
	lines = list(section_injector(iter([])))
	assert lines[0] == '[messages]\n'


def testSectionInjectorYieldsFileContentsAfterHeader():
	lines = list(section_injector(iter(['a = 1\n', 'b = 2\n'])))
	assert lines[1] == 'a = 1\n'
	assert lines[2] == 'b = 2\n'

#-------------------------------------------------------------------------------
# _clean

def testCleanStripsDoubleQuotes():
	assert _clean('"Hello"') == 'Hello'

def testCleanLeavesUnquotedValueUnchanged():
	assert _clean('Hello') == 'Hello'


#-------------------------------------------------------------------------------
# Localizer.get_message

def testLocalizerGetMessageFindsInFirstSource():
	localizer = Localizer([{'greeting': 'Hello'}, {'greeting': 'Fallback'}])
	assert localizer.get_message('greeting') == 'Hello'


def testLocalizerGetMessageFallsThroughToSecondSource():
	localizer = Localizer([{}, {'greeting': 'Fallback'}])
	assert localizer.get_message('greeting') == 'Fallback'


def testLocalizerGetMessageIsCaseInsensitive():
	localizer = Localizer([{'greeting': 'Hello'}])
	assert localizer.get_message('GREETING') == 'Hello'


def testLocalizerGetMessageCleansQuotedValues():
	localizer = Localizer([{'greeting': '"Hello"'}])
	assert localizer.get_message('greeting') == 'Hello'


def testLocalizerGetMessageWarnsAndReturnsUnknownWhenMissing():
	localizer = Localizer([{}])
	with patch('pavao.i18n.Logger') as mock_logger:
		result = localizer.get_message('missing')
	assert result == '<Unknown>'
	mock_logger.warning.assert_called_once()
	assert 'missing' in mock_logger.warning.call_args.args[0]

#-------------------------------------------------------------------------------
# Localizer.create_error

def testLocalizerCreateErrorReturnsDict():
	localizer = Localizer([{'err.notfound': 'Not found'}])
	error = localizer.create_error('err.notfound')
	assert error['error'] == 'err.notfound'
	assert error['description'] == 'Not found'
	assert 'timestamp' in error


def testLocalizerCreateErrorTimestampIsUtc():
	localizer = Localizer([{'err.notfound': 'Not found'}])
	error = localizer.create_error('err.notfound')
	assert error['timestamp'].tzinfo == timezone.utc

#-------------------------------------------------------------------------------
# Localizer.assign_response_error

def testLocalizerAssignResponseErrorSerializesAndSetsContent():
	localizer = Localizer([{'err.bad': 'Bad request'}])
	response = MagicMock()

	with patch('pavao.i18n.error_blueprint') as mock_bp:
		mock_bp.serialize.return_value = '{"error":"err.bad"}'
		localizer.assign_response_error(response, 'err.bad')

	mock_bp.serialize.assert_called_once()
	response.set_content.assert_called_once()
	args = response.set_content.call_args.args
	assert args[0] == 'application/json'
	assert isinstance(args[1], bytes)

#-------------------------------------------------------------------------------
# Internationalization.__init__

def testInternationalizationLoadsIniFiles(tmp_path):
	make_i18n_dir(tmp_path, {
		'en_US': {'greeting': 'Hello'},
		'pt_BR': {'greeting': 'Olá'},
	})
	i18n = Internationalization(str(tmp_path))
	assert 'en_US' in i18n.languages
	assert 'pt_BR' in i18n.languages


def testInternationalizationSetsFallback(tmp_path):
	make_i18n_dir(tmp_path, {'en_US': {'greeting': 'Hello'}})
	i18n = Internationalization(str(tmp_path), fallback_language='en_US')
	assert i18n.fallback == i18n.languages['en_US']


def testInternationalizationFallbackEmptyWhenNoMatch(tmp_path):
	make_i18n_dir(tmp_path, {'pt_BR': {'greeting': 'Olá'}})
	i18n = Internationalization(str(tmp_path), fallback_language='en_US')
	assert i18n.fallback == {}


def testInternationalizationIgnoresNonIniFiles(tmp_path):
	make_i18n_dir(tmp_path, {'en_US': {'greeting': 'Hello'}})
	(tmp_path / 'README.txt').write_text('ignore me')
	i18n = Internationalization(str(tmp_path))
	assert 'README' not in i18n.languages


def testInternationalizationHandlesEmptyDirectory(tmp_path):
	i18n = Internationalization(str(tmp_path))
	assert i18n.languages == {}
	assert i18n.fallback == {}

#-------------------------------------------------------------------------------
# Internationalization.localize

def testLocalizeExactLanguageMatch(tmp_path):
	make_i18n_dir(tmp_path, {'en_US': {'greeting': 'Hello'}})
	i18n = Internationalization(str(tmp_path))
	assert i18n.localize('en_US', 'greeting') == 'Hello'


def testLocalizeIsCaseInsensitiveOnMessageId(tmp_path):
	make_i18n_dir(tmp_path, {'en_US': {'greeting': 'Hello'}})
	i18n = Internationalization(str(tmp_path))
	assert i18n.localize('en_US', 'GREETING') == 'Hello'


def testLocalizeCleansQuotedValues(tmp_path):
	make_i18n_dir(tmp_path, {'en_US': {'greeting': '"Hello"'}})
	i18n = Internationalization(str(tmp_path))
	assert i18n.localize('en_US', 'greeting') == 'Hello'


def testLocalizeFuzzyMatchPrefixLanguage(tmp_path):
	# request "en" should match existing "en_US"
	make_i18n_dir(tmp_path, {'en_US': {'greeting': 'Hello'}})
	i18n = Internationalization(str(tmp_path))
	assert i18n.localize('en', 'greeting') == 'Hello'


def testLocalizeFallsBackToFallbackLanguage(tmp_path):
	make_i18n_dir(tmp_path, {
		'en_US': {'greeting': 'Hello'},
		'pt_BR': {},
	})
	i18n = Internationalization(str(tmp_path), fallback_language='en_US')
	assert i18n.localize('pt_BR', 'greeting') == 'Hello'


def testLocalizeWarnsAndReturnsUnknownWhenMissing(tmp_path):
	make_i18n_dir(tmp_path, {'en_US': {}})
	i18n = Internationalization(str(tmp_path))
	with patch('pavao.i18n.Logger') as mock_logger:
		result = i18n.localize('en_US', 'missing')
	assert result == '<Unknown>'
	mock_logger.warning.assert_called_once()


def testLocalizeUnknownLanguageUsesOnlyFallback(tmp_path):
	make_i18n_dir(tmp_path, {'en_US': {'greeting': 'Hello'}})
	i18n = Internationalization(str(tmp_path), fallback_language='en_US')
	assert i18n.localize('zh_CN', 'greeting') == 'Hello'

#-------------------------------------------------------------------------------
# Internationalization.create_localizer

def testCreateLocalizerEmptyPriorityUsesFallback(tmp_path):
	make_i18n_dir(tmp_path, {'en_US': {'greeting': 'Hello'}})
	i18n = Internationalization(str(tmp_path), fallback_language='en_US')
	localizer = i18n.create_localizer([])
	assert localizer.get_message('greeting') == 'Hello'


def testCreateLocalizerWithKnownLanguage(tmp_path):
	make_i18n_dir(tmp_path, {
		'en_US': {'greeting': 'Hello'},
		'pt_BR': {'greeting': 'Olá'},
	})
	i18n = Internationalization(str(tmp_path), fallback_language='en_US')
	localizer = i18n.create_localizer(['pt_BR'])
	assert localizer.get_message('greeting') == 'Olá'


def testCreateLocalizerUnknownLanguageSkipped(tmp_path):
	make_i18n_dir(tmp_path, {'en_US': {'greeting': 'Hello'}})
	i18n = Internationalization(str(tmp_path), fallback_language='en_US')
	localizer = i18n.create_localizer(['zh_CN'])
	# zh_CN unknown → only fallback → returns en_US greeting
	assert localizer.get_message('greeting') == 'Hello'


def testCreateLocalizerFallbackNotDuplicated(tmp_path):
	make_i18n_dir(tmp_path, {'en_US': {'greeting': 'Hello'}})
	i18n = Internationalization(str(tmp_path), fallback_language='en_US')
	localizer = i18n.create_localizer(['en_US'])
	assert localizer.sources.count(i18n.fallback) == 1


def testCreateLocalizerPriorityOrderRespected(tmp_path):
	make_i18n_dir(tmp_path, {
		'en_US': {'greeting': 'Hello'},
		'pt_BR': {'greeting': 'Olá'},
	})
	i18n = Internationalization(str(tmp_path), fallback_language='en_US')
	localizer = i18n.create_localizer(['pt_BR', 'en_US'])
	assert localizer.get_message('greeting') == 'Olá'

#-------------------------------------------------------------------------------
# LazyLocalizer

def testLazyLocalizerIdentity():
	ll = LazyLocalizer(MagicMock(), 'mymodule', 'greeting')
	assert ll.identity() == 'mymodule::greeting'


def testLazyLocalizerLocalizeDelegates():
	mock_i18n = MagicMock()
	mock_localizer = MagicMock()
	mock_i18n.create_localizer.return_value = mock_localizer
	mock_localizer.get_message.return_value = 'Hello'

	ll = LazyLocalizer(mock_i18n, 'mymodule', 'greeting')
	result = ll.localize(['en_US'])

	mock_i18n.create_localizer.assert_called_once_with(['en_US'])
	mock_localizer.get_message.assert_called_once_with('greeting')
	assert result == 'Hello'

#-------------------------------------------------------------------------------
# ModuleLocalizer

def testModuleLocalizerMapReturnsLazyLocalizer(tmp_path):
	ml = ModuleLocalizer('mymodule', str(tmp_path))
	ll = ml.map('greeting')
	assert isinstance(ll, LazyLocalizer)
	assert ll.module == 'mymodule'
	assert ll.fragment == 'greeting'


def testModuleLocalizerMapPreservesI18nReference(tmp_path):
	ml = ModuleLocalizer('mymodule', str(tmp_path))
	ll = ml.map('greeting')
	assert ll.localizer is ml.localizer

#-------------------------------------------------------------------------------

if __name__ == "__main__":
	import pytest
	pytest.main([__file__, "-v"])
