
import logging
import asyncio
import threading
import datetime

def time_now():
	currently = datetime.datetime.now(datetime.timezone.utc)
	millisecs = currently.microsecond / 1000
	return currently.strftime(f"%Y-%m-%d %H:%M:%S.{millisecs:03.0f} %Z")

_logLoop = None
_logThread = None
_logQueue = None

# adapted from
# https://stackoverflow.com/a/63859696
# by user4815162342

def _scheduleLog(contents):
	startLogging()

	global _logLoop, _logQueue
	_logLoop.call_soon_threadsafe(
		_logQueue.put_nowait,
		contents)


def _logPublisher(readyEvent):
	async def publishingLoop():
		global _logLoop, _logQueue
		_logLoop = asyncio.get_running_loop()
		_logQueue = asyncio.Queue()
		readyEvent.set()

		while True:
			new_message = await _logQueue.get()
			if "__exit__" == new_message:
				_logQueue.task_done()
				break

			fnc, level_str, text, time_str = new_message
			final_msg = f"({time_str}) [{level_str}] {text}"
			fnc(final_msg)

			_logQueue.task_done()

	asyncio.run(publishingLoop())

#-------------------------------------------------------------------------------

def startLogging():
	global _logThread
	if None != _logThread:
		return

	readyEvent = threading.Event()
	_logThread = threading.Thread(
		target=_logPublisher,
		args=(readyEvent,))

	logging.basicConfig(
		filename="teste.log",
		format='%(message)s',
		level=logging.DEBUG)

	logging.getLogger().addHandler(logging.StreamHandler())
	_logThread.start()
	readyEvent.wait()


def stopLogging():
	global _logThread, _logQueue

	if None != _logThread:
		_scheduleLog("__exit__")
		_logThread.join()
		_logThread = None
		_logQueue = None

#-------------------------------------------------------------------------------

def critical(msg): _scheduleLog((logging.critical, "CRITICAL", msg, time_now()))
def error(msg):    _scheduleLog((logging.error,    "ERROR",    msg, time_now()))
def warning(msg):  _scheduleLog((logging.warning,  "WARNING",  msg, time_now()))
def info(msg):     _scheduleLog((logging.info,     "INFO",     msg, time_now()))
def debug(msg):    _scheduleLog((logging.debug,    "DEBUG",    msg, time_now()))

#-------------------------------------------------------------------------------

startLogging()

while True:
	cmd = input("Insert something: ")
	if cmd == "exit":
		break

	critical(cmd)
	error(cmd)
	warning(cmd)
	info(cmd)
	debug(cmd)

stopLogging()

