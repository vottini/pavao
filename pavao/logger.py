
import logging
import threading
import datetime
import queue

from .exception import PavaoException

def _time_now():
	currently = datetime.datetime.now(datetime.timezone.utc)
	millisecs = currently.microsecond / 1000
	return currently.strftime(f"%Y-%m-%d %H:%M:%S.{millisecs:03.0f} %Z")

_log_thread = None
_log_queue = queue.Queue()

def _schedule_log(contents):
	global _log_queue
	_log_queue.put(contents)

def logging_loop(ready_event):
	global _log_queue
	ready_event.set()

	text = "Logging thread started"
	initial_msg = f"({_time_now()}) [INFO] {text}"
	logging.info(initial_msg)

	while True:
		new_message = _log_queue.get()
		if "__exit__" == new_message:
			_log_queue.task_done()
			break

		log_function, level_str, text, time_str = new_message
		final_msg = f"({time_str}) [{level_str}] {text}"
		log_function(final_msg)
		_log_queue.task_done()

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

def start_logging(settings):
	global _log_queue, _log_thread
	if _log_thread is not None:
		return

	log_settings = settings.get_setting(
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

	ready_event = threading.Event()
	logging.getLogger().addHandler(logging.StreamHandler())
	_log_thread = threading.Thread(target=logging_loop, args=(ready_event,))
	_log_thread.start()
	ready_event.wait()


def stop_logging():
	global _log_thread
	if _log_thread is not None:
		_schedule_log("__exit__")
		_log_thread.join()
		_log_thread = None

#-------------------------------------------------------------------------------

class Logger:
	@staticmethod
	def critical(msg):
		_schedule_log((
			logging.critical, "CRITICAL",
			msg, _time_now()))

	@staticmethod
	def error(msg):
		_schedule_log((
			logging.error, "ERROR",
			msg, _time_now()))

	@staticmethod
	def warning(msg):
		_schedule_log((
			logging.warning, "WARNING",
			msg, _time_now()))

	@staticmethod
	def info(msg):
		_schedule_log((
			logging.info, "INFO",
			msg, _time_now()))

	@staticmethod
	def debug(msg):
		_schedule_log((
			logging.debug, "DEBUG",
			msg, _time_now()))

#-------------------------------------------------------------------------------

__all__ = [
	"start_logging",
	"stop_logging",
	"Logger"
]

