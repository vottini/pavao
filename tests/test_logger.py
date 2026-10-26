
import sys
sys.path.append('..')

import logging
import pytest
import pavao.logger as logger_module
from pavao.logger import Logger, start_logging, stop_logging

#-------------------------------------------------------------------------------

class MockSettings:
	def __init__(self, level="INFO", dir=None, file=None, max_size=None, schedule=None, backup_count=10):
		self._level        = level
		self._dir          = dir      or "logs"
		self._file         = file     or ""
		self._max_size     = max_size or ""
		self._schedule     = schedule or ""
		self._backup_count = backup_count

	def get_setting(self, key, schema):
		return {
			"level": self._level,
			"persist": {
				"dir":          self._dir,
				"file":         self._file,
				"max_size":     self._max_size,
				"schedule":     self._schedule,
				"backup_count": self._backup_count,
			}
		}

@pytest.fixture(autouse=True)
def reset_logger(tmp_path):
	yield
	stop_logging()
	logger_module._logger.handlers.clear()
	logger_module._logger.propagate = True

#-------------------------------------------------------------------------------

def testStartLoggingAttachesHandler():
	start_logging(MockSettings())
	assert any(isinstance(h, logging.handlers.QueueHandler)
		for h in logger_module._logger.handlers)

def testStartLoggingIdempotent():
	settings = MockSettings()
	start_logging(settings)
	start_logging(settings)
	handler_count = sum(1 for h in logger_module._logger.handlers
		if isinstance(h, logging.handlers.QueueHandler))
	assert handler_count == 1

def testStopLoggingClearsListener():
	start_logging(MockSettings())
	stop_logging()
	assert logger_module._listener is None

def testStopLoggingIdempotent():
	start_logging(MockSettings())
	stop_logging()
	stop_logging()  # must not raise

def testUnrecognizedLevelFallsBackToInfo(capsys):
	start_logging(MockSettings(level="VERBOSE"))
	assert logger_module._logger.level == logging.INFO
	captured = capsys.readouterr()
	assert "VERBOSE" in captured.err

def testLogLevels():
	for level_str, expected in [
		("DEBUG",  logging.DEBUG),
		("INFO",   logging.INFO),
		("WARN",   logging.WARNING),
		("ERROR",  logging.ERROR),
		("FATAL",  logging.CRITICAL),
	]:
		stop_logging()
		logger_module._logger.handlers.clear()
		start_logging(MockSettings(level=level_str))
		assert logger_module._logger.level == expected

def testLoggerMethodsDoNotRaiseBeforeStart():
	# Messages before start_logging are silently discarded — must not raise
	Logger.info("pre-start info")
	Logger.warning("pre-start warning")
	Logger.error("pre-start error")

def testNoFileByDefault(tmp_path):
	start_logging(MockSettings())
	listener = logger_module._listener
	assert not any(
		isinstance(h, (logging.FileHandler, logging.handlers.RotatingFileHandler))
		for h in listener.handlers)

def testLoggerWritesToFile(tmp_path):
	start_logging(MockSettings(dir=str(tmp_path), file="output.log"))
	Logger.info("hello from test")
	stop_logging()
	content = (tmp_path / "output.log").read_text()
	assert "hello from test" in content
	assert "[INFO]" in content

def testFormatterIncludesTimestamp(tmp_path):
	start_logging(MockSettings(dir=str(tmp_path), file="output.log"))
	Logger.error("timestamp check")
	stop_logging()
	content = (tmp_path / "output.log").read_text()
	assert "UTC" in content
	assert "[ERROR]" in content

def testStopLoggingFlushesQueue(tmp_path):
	start_logging(MockSettings(dir=str(tmp_path), file="output.log"))
	for i in range(20):
		Logger.info(f"message {i}")
	stop_logging()
	content = (tmp_path / "output.log").read_text()
	assert "message 19" in content

def testLogDirIsCreated(tmp_path):
	log_dir = tmp_path / "nested" / "logs"
	start_logging(MockSettings(dir=str(log_dir), file="output.log"))
	stop_logging()
	assert log_dir.is_dir()

def testSizeRotation(tmp_path):
	start_logging(MockSettings(dir=str(tmp_path), file="output.log", max_size="1KB"))
	listener = logger_module._listener
	assert any(isinstance(h, logging.handlers.RotatingFileHandler)
		for h in listener.handlers)

def testSizeRotationBackupCount(tmp_path):
	start_logging(MockSettings(dir=str(tmp_path), file="output.log", max_size="1KB", backup_count=3))
	listener = logger_module._listener
	handler = next(h for h in listener.handlers
		if isinstance(h, logging.handlers.RotatingFileHandler))
	assert handler.backupCount == 3

def testScheduleRotation(tmp_path):
	start_logging(MockSettings(dir=str(tmp_path), file="output.log", schedule="0 0 * * *"))
	listener = logger_module._listener
	assert any(isinstance(h, logger_module._CronRotatingFileHandler)
		for h in listener.handlers)

def testScheduleRotationBackupCount(tmp_path):
	start_logging(MockSettings(dir=str(tmp_path), file="output.log", schedule="0 0 * * *", backup_count=5))
	listener = logger_module._listener
	handler = next(h for h in listener.handlers
		if isinstance(h, logger_module._CronRotatingFileHandler))
	assert handler.backupCount == 5

def testBothSetMaxSizeWins(tmp_path, capsys):
	start_logging(MockSettings(dir=str(tmp_path), file="output.log", max_size="1MB", schedule="0 0 * * *"))
	listener = logger_module._listener
	assert any(isinstance(h, logging.handlers.RotatingFileHandler)
		for h in listener.handlers)
	assert not any(isinstance(h, logger_module._CronRotatingFileHandler)
		for h in listener.handlers)
	assert "max_size" in capsys.readouterr().err

def testInvalidMaxSizeDisablesFile(tmp_path, capsys):
	start_logging(MockSettings(dir=str(tmp_path), file="output.log", max_size="notasize"))
	listener = logger_module._listener
	assert not any(isinstance(h, logging.FileHandler) for h in listener.handlers)
	assert "Invalid max_size" in capsys.readouterr().err

def testInvalidScheduleDisablesFile(tmp_path, capsys):
	start_logging(MockSettings(dir=str(tmp_path), file="output.log", schedule="not a cron"))
	listener = logger_module._listener
	assert not any(isinstance(h, logging.FileHandler) for h in listener.handlers)
	assert "Invalid cron schedule" in capsys.readouterr().err

def testParseSizeUnits():
	from pavao.logger import _parse_size
	assert _parse_size("1KB")  == 1024
	assert _parse_size("2MB")  == 2 * 1024**2
	assert _parse_size("1GB")  == 1024**3
	assert _parse_size("500")  == 500
	assert _parse_size("bad")  is None

#-------------------------------------------------------------------------------

if __name__ == "__main__":
	import tempfile, pathlib
	with tempfile.TemporaryDirectory() as d:
		tmp = pathlib.Path(d)
		testStartLoggingAttachesHandler()
		testStartLoggingIdempotent()
		testStopLoggingClearsListener()
		testStopLoggingIdempotent()
		testLoggerMethodsDoNotRaiseBeforeStart()
		testNoFileByDefault(tmp)
		testLoggerWritesToFile(tmp)
		testFormatterIncludesTimestamp(tmp)
		testStopLoggingFlushesQueue(tmp)
		testSizeRotation(tmp)
		testScheduleRotation(tmp)
		testBothSetMaxSizeWins(tmp)
		testInvalidMaxSizeDisablesFile(tmp)
		testInvalidScheduleDisablesFile(tmp)
		testParseSizeUnits()
