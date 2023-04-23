
import logging
import threading
import datetime
import queue

def time_now():
	currently = datetime.datetime.now(datetime.timezone.utc)
	millisecs = currently.microsecond / 1000
	return currently.strftime(f"%Y-%m-%d %H:%M:%S.{millisecs:03.0f} %Z")

_logThread = None
_logQueue = queue.Queue()

def _scheduleLog(contents):
	global _logQueue
	startLogging()
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

#-------------------------------------------------------------------------------

def startLogging():
	global _logQueue, _logThread
	if None != _logThread:
		return

	logging.basicConfig(
		filename="teste.log",
		format='%(message)s',
		level=logging.DEBUG)

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

def critical(msg): _scheduleLog((logging.critical, "CRITICAL", msg, time_now()))
def error(msg):    _scheduleLog((logging.error,    "ERROR",    msg, time_now()))
def warning(msg):  _scheduleLog((logging.warning,  "WARNING",  msg, time_now()))
def info(msg):     _scheduleLog((logging.info,     "INFO",     msg, time_now()))
def debug(msg):    _scheduleLog((logging.debug,    "DEBUG",    msg, time_now()))

#-------------------------------------------------------------------------------

#startLogging()
#
#while True:
#	cmd = input("Insert something: ")
#	if cmd == "exit":
#		break
#
#	critical(cmd)
#	error(cmd)
#	warning(cmd)
#	info(cmd)
#	debug(cmd)
#
#stopLogging()

__all__ = [
	"startLogging",
	"stopLogging",
	"critical",
	"error",
	"warning",
	"info",
	"debug"
]


