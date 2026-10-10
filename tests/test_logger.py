
import sys
sys.path.append('..')

import logging
import pytest
import pavao.logger as logger_module
from pavao.logger import Logger, start_logging, stop_logging

#-------------------------------------------------------------------------------

class MockSettings:
	def __init__(self, level="INFO", output=None, persist=True):
		self._level = level
		self._output = output
		self._persist = persist

	def get_setting(self, key, schema):
		return {
			"level": self._level,
			"output": self._output or schema["output"],
			"persist": self._persist,
		}

@pytest.fixture(autouse=True)
def reset_logger(tmp_path):
	yield
	stop_logging()
	logger_module._logger.handlers.clear()
	logger_module._logger.propagate = True

#-------------------------------------------------------------------------------

def testStartLoggingAttachesHandler(tmp_path):
	settings = MockSettings(output=str(tmp_path / "test.log"))
	start_logging(settings)
	assert any(isinstance(h, logging.handlers.QueueHandler)
		for h in logger_module._logger.handlers)

def testStartLoggingIdempotent(tmp_path):
	settings = MockSettings(output=str(tmp_path / "test.log"))
	start_logging(settings)
	start_logging(settings)
	handler_count = sum(1 for h in logger_module._logger.handlers
		if isinstance(h, logging.handlers.QueueHandler))
	assert handler_count == 1

def testStopLoggingClearsListener(tmp_path):
	settings = MockSettings(output=str(tmp_path / "test.log"))
	start_logging(settings)
	stop_logging()
	assert logger_module._listener is None

def testStopLoggingIdempotent(tmp_path):
	settings = MockSettings(output=str(tmp_path / "test.log"))
	start_logging(settings)
	stop_logging()
	stop_logging()  # must not raise

def testUnrecognizedLevelFallsBackToInfo(tmp_path, capsys):
	settings = MockSettings(level="VERBOSE", output=str(tmp_path / "test.log"))
	start_logging(settings)
	assert logger_module._logger.level == logging.INFO
	captured = capsys.readouterr()
	assert "VERBOSE" in captured.err

def testLogLevels(tmp_path):
	for level_str, expected in [
		("DEBUG",  logging.DEBUG),
		("INFO",   logging.INFO),
		("WARN",   logging.WARNING),
		("ERROR",  logging.ERROR),
		("FATAL",  logging.CRITICAL),
	]:
		stop_logging()
		logger_module._logger.handlers.clear()
		settings = MockSettings(level=level_str, output=str(tmp_path / "test.log"))
		start_logging(settings)
		assert logger_module._logger.level == expected

def testLoggerMethodsDoNotRaiseBeforeStart():
	# Messages before start_logging are silently discarded — must not raise
	Logger.info("pre-start info")
	Logger.warning("pre-start warning")
	Logger.error("pre-start error")

def testLoggerWritesToFile(tmp_path):
	log_file = tmp_path / "output.log"
	settings = MockSettings(output=str(log_file))
	start_logging(settings)

	Logger.info("hello from test")
	stop_logging()

	assert log_file.exists()
	content = log_file.read_text()
	assert "hello from test" in content
	assert "[INFO]" in content

def testFormatterIncludesTimestamp(tmp_path):
	log_file = tmp_path / "output.log"
	settings = MockSettings(output=str(log_file))
	start_logging(settings)

	Logger.error("timestamp check")
	stop_logging()

	content = log_file.read_text()
	# format: (YYYY-MM-DD HH:MM:SS.mmm UTC) [ERROR] ...
	assert "UTC" in content
	assert "[ERROR]" in content

def testStopLoggingFlushesQueue(tmp_path):
	log_file = tmp_path / "output.log"
	settings = MockSettings(output=str(log_file))
	start_logging(settings)

	for i in range(20):
		Logger.info(f"message {i}")
	stop_logging()  # must drain before returning

	content = log_file.read_text()
	assert "message 19" in content

#-------------------------------------------------------------------------------

if __name__ == "__main__":
	import tempfile, pathlib
	with tempfile.TemporaryDirectory() as d:
		tmp = pathlib.Path(d)
		testStartLoggingAttachesHandler(tmp)
		testStartLoggingIdempotent(tmp)
		testStopLoggingClearsListener(tmp)
		testStopLoggingIdempotent(tmp)
		testLoggerMethodsDoNotRaiseBeforeStart()
		testLoggerWritesToFile(tmp)
		testFormatterIncludesTimestamp(tmp)
		testStopLoggingFlushesQueue(tmp)
