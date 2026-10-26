
import queue
import logging
import logging.handlers
import datetime

from croniter import croniter
from .exception import PavaoException

#-------------------------------------------------------------------------------

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


class _CronRotatingFileHandler(logging.handlers.TimedRotatingFileHandler):
	def __init__(self, filename, schedule, backup_count):
		self._cron_schedule = schedule
		super().__init__(filename, when='S', backupCount=backup_count)

	def computeRollover(self, currentTime):
		it = croniter(self._cron_schedule, datetime.datetime.fromtimestamp(currentTime))
		return it.get_next(float)


def _parse_size(size_str):
	size_str = size_str.strip()
	for suffix, factor in [("GB", 1024**3), ("MB", 1024**2), ("KB", 1024)]:
		if size_str.upper().endswith(suffix):
			try:
				return int(float(size_str[:-len(suffix)]) * factor)
			except ValueError:
				return None
	try:
		return int(size_str)
	except ValueError:
		return None

#-------------------------------------------------------------------------------

_logging_schema = {
	"level": "INFO",
	"persist": {
		"dir":          "logs",
		"file":         "",
		"max_size":     "",
		"schedule":     "",
		"backup_count": 10,
	}
}

_logger   = logging.getLogger('pavao')
_listener = None

def start_logging(settings):
	global _listener

	if _listener is not None:
		return

	import sys

	log_settings = settings.get_setting("pavao.logging", _logging_schema)

	level_str = log_settings['level']
	log_level = _logging_levels.get(level_str)
	if log_level is None:
		print(f"Unrecognized log level '{level_str}', using INFO", file=sys.stderr)
		log_level = logging.INFO

	persist      = log_settings['persist']
	persist_dir          = persist['dir']
	persist_file         = persist['file']
	persist_max_size     = persist['max_size']
	persist_schedule     = persist['schedule']
	persist_backup_count = persist['backup_count']

	formatter = _Formatter()
	handlers = [logging.StreamHandler()]

	if persist_file:
		import os
		os.makedirs(persist_dir, exist_ok=True)
		persist_file = os.path.join(persist_dir, persist_file)
		if persist_max_size and persist_schedule:
			print("Both max_size and schedule set for log rotation; max_size takes priority", file=sys.stderr)
			persist_schedule = ""

		if persist_max_size:
			max_bytes = _parse_size(persist_max_size)
			if max_bytes is None:
				print(f"Invalid max_size '{persist_max_size}', file logging disabled", file=sys.stderr)
			else:
				handlers.append(logging.handlers.RotatingFileHandler(
					persist_file, maxBytes=max_bytes, backupCount=persist_backup_count))

		elif persist_schedule:
			if not croniter.is_valid(persist_schedule):
				print(f"Invalid cron schedule '{persist_schedule}', file logging disabled", file=sys.stderr)
			else:
				handlers.append(_CronRotatingFileHandler(
					persist_file, persist_schedule, persist_backup_count))

		else:
			handlers.append(logging.FileHandler(persist_file))

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
