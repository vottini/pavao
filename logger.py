
import asyncio
import threading
import logging

_logLoop = None
_logThread = None
_logQueue = None

# adapted from
# https://stackoverflow.com/a/63859696
# by user4815162342

def _scheduleLog(message):
	global _logLoop, _logQueue
	if None != _logLoop:
		_logLoop.call_soon_threadsafe(
			_logQueue.put_nowait,
			message)


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

			#print("LOG " + new_message)
			logging.info(new_message)
			_logQueue.task_done()

	asyncio.run(publishingLoop())

#-------------------------------------------------------------------------------

def startLogging():
	global _logThread

	if None == _logThread:
		readyEvent = threading.Event()
		_logThread = threading.Thread(
			target=_logPublisher,
			args=(readyEvent,))

		logging.basicConfig(
			filename="teste.log",
			format='(%(asctime)s) [%(levelname)s] %(message)s',
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



#-------------------------------------------------------------------------------

startLogging()

while True:
	cmd = input("Insert something: ")
	if cmd == "exit":
		break

	_scheduleLog(cmd)

stopLogging()

