
import logging
import threading
import datetime
import queue

from .exception import PavaoException

def _time_now():
	currently = datetime.datetime.now(datetime.timezone.utc)
	millisecs = currently.microsecond / 1000
	return currently.strftime(f"%Y-%m-%d %H:%M:%S.{millisecs:03.0f} %Z")

_logThread = None
_logQueue = queue.Queue()

def _scheduleLog(contents):
	global _logQueue
	_logQueue.put(contents)

def loggingLoop(readyEvent):
	global _logQueue
	readyEvent.set()

	while True:
		new_message = _logQueue.get()
		if "__exit__" == new_message:
			_logQueue.task_done()
			break

		log_function, level_str, text, time_str = new_message
		final_msg = f"({time_str}) [{level_str}] {text}"
		log_function(final_msg)
		_logQueue.task_done()

	text = "Logging thread finished"
	final_msg = f"({_time_now()}) [INFO] {text}"
	logging.info(final_msg)

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

def startLogging(settings):
	global _logQueue, _logThread
	if None != _logThread:
		return

	log_settings = settings.getSetting(
		"pavao.logging",
		_logging_schema)

	log_level = log_settings['level']
	if not log_level in _logging_levels:
		Logger.warning(f"Unrecognized log level '{log_level}', using default 'INFO'")
		log_level = "INFO"

	logging.basicConfig(
		filename=log_settings['output'],
		level=_logging_levels[log_level],
		format='%(message)s')

	readyEvent = threading.Event()
	logging.getLogger().addHandler(logging.StreamHandler())
	_logThread = threading.Thread(target=loggingLoop, args=(readyEvent,))
	_logThread.start()
	readyEvent.wait()


def stopLogging():
	global _logThread
	if None != _logThread:
		_scheduleLog("__exit__")
		_logThread.join()
		_logThread = None

#-------------------------------------------------------------------------------

class Logger:
	@staticmethod
	def critical(msg):
		_scheduleLog((
			logging.critical, "CRITICAL",
			msg, _time_now()))

	@staticmethod
	def error(msg):
		_scheduleLog((
			logging.error, "ERROR",
			msg, _time_now()))

	@staticmethod
	def warning(msg):
		_scheduleLog((
			logging.warning, "WARNING",
			msg, _time_now()))

	@staticmethod
	def info(msg):
		_scheduleLog((
			logging.info, "INFO",
			msg, _time_now()))

	@staticmethod
	def debug(msg):
		_scheduleLog((
			logging.debug, "DEBUG",
			msg, _time_now()))

#-------------------------------------------------------------------------------

__all__ = [
	"startLogging",
	"stopLogging",
	"Logger"
]

