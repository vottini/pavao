
import queue
import logging
import logging.handlers
import datetime

from .exception import PavaoException

#-------------------------------------------------------------------------------

_logging_schema = {
	"output": "pavao.log",
	"level": "INFO"
}

_logging_levels = {
	"FATAL": logging.CRITICAL,
	"ERROR": logging.ERROR,
	"WARN":  logging.WARNING,
	"INFO":  logging.INFO,
	"DEBUG": logging.DEBUG
}

#-------------------------------------------------------------------------------

class _Formatter(logging.Formatter):
	def format(self, record):
		dt = datetime.datetime.fromtimestamp(record.created, tz=datetime.timezone.utc)
		ms = dt.microsecond // 1000
		timestamp = dt.strftime(f"%Y-%m-%d %H:%M:%S.{ms:03d} %Z")
		return f"({timestamp}) [{record.levelname}] {record.getMessage()}"

#-------------------------------------------------------------------------------

_logger   = logging.getLogger('pavao')
_listener = None

def start_logging(settings):
	global _listener

	if _listener is not None:
		return

	log_settings = settings.get_setting("pavao.logging", _logging_schema)

	log_level_str = log_settings['level']
	log_level = _logging_levels.get(log_level_str)
	if log_level is None:
		import sys
		print(f"Unrecognized log level '{log_level_str}', using INFO", file=sys.stderr)
		log_level = logging.INFO

	formatter = _Formatter()
	handlers = [
		logging.StreamHandler(),
		logging.FileHandler(log_settings['output']),
	]
	for h in handlers:
		h.setFormatter(formatter)

	log_queue = queue.SimpleQueue()
	queue_handler = logging.handlers.QueueHandler(log_queue)

	_logger.addHandler(queue_handler)
	_logger.setLevel(log_level)
	_logger.propagate = False

	_listener = logging.handlers.QueueListener(log_queue, *handlers, respect_handler_level=True)
	_listener.start()


def stop_logging():
	global _listener
	if _listener is not None:
		_listener.stop()
		_listener = None

#-------------------------------------------------------------------------------

class Logger:
	@staticmethod
	def critical(msg): _logger.critical(msg)

	@staticmethod
	def error(msg): _logger.error(msg)

	@staticmethod
	def warning(msg): _logger.warning(msg)

	@staticmethod
	def info(msg): _logger.info(msg)

	@staticmethod
	def debug(msg): _logger.debug(msg)

#-------------------------------------------------------------------------------

__all__ = [
	"start_logging",
	"stop_logging",
	"Logger"
]
