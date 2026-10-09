
import sys
sys.path.append('..')

import asyncio
import pytest
from unittest.mock import MagicMock, patch, call

from pavao.refresher import Modifications, SimulatedEvent, PathMonitor

#-------------------------------------------------------------------------------
# Modifications — add_creation

def testAddCreationNewFile():
	m = Modifications().add_creation('/a.py')
	assert '/a.py' in m.creations
	assert '/a.py' not in m.deletions
	assert '/a.py' not in m.updates


def testAddCreationIdempotentWhenAlreadyInCreations():
	m = Modifications().add_creation('/a.py')
	m2 = m.add_creation('/a.py')
	assert m2 is m


def testAddCreationIdempotentWhenAlreadyInUpdates():
	m = Modifications(updates=('/a.py',))
	m2 = m.add_creation('/a.py')
	assert m2 is m


def testAddCreationAfterDeletionBecomesUpdate():
	m = Modifications(deletions=('/a.py',)).add_creation('/a.py')
	assert '/a.py' in m.updates
	assert '/a.py' not in m.deletions
	assert '/a.py' not in m.creations


def testAddCreationPreservesOtherEntries():
	m = Modifications(creations=('/b.py',)).add_creation('/a.py')
	assert '/b.py' in m.creations
	assert '/a.py' in m.creations

#-------------------------------------------------------------------------------
# Modifications — add_deletion

def testAddDeletionNewFile():
	m = Modifications().add_deletion('/a.py')
	assert '/a.py' in m.deletions


def testAddDeletionIdempotentWhenAlreadyInDeletions():
	m = Modifications(deletions=('/a.py',))
	m2 = m.add_deletion('/a.py')
	assert m2 is m


def testAddDeletionAfterCreationDisappears():
	m = Modifications(creations=('/a.py',)).add_deletion('/a.py')
	assert '/a.py' not in m.creations
	assert '/a.py' not in m.deletions
	assert '/a.py' not in m.updates


def testAddDeletionAfterUpdateBecomesDeleted():
	m = Modifications(updates=('/a.py',)).add_deletion('/a.py')
	assert '/a.py' in m.deletions
	assert '/a.py' not in m.updates


def testAddDeletionPreservesOtherEntries():
	m = Modifications(creations=('/b.py',)).add_deletion('/a.py')
	assert '/b.py' in m.creations
	assert '/a.py' in m.deletions

#-------------------------------------------------------------------------------
# Modifications — add_update

def testAddUpdateNewFile():
	m = Modifications().add_update('/a.py')
	assert '/a.py' in m.updates


def testAddUpdateIdempotentWhenAlreadyInUpdates():
	m = Modifications(updates=('/a.py',))
	m2 = m.add_update('/a.py')
	assert m2 is m


def testAddUpdateIdempotentWhenInCreations():
	m = Modifications(creations=('/a.py',))
	m2 = m.add_update('/a.py')
	assert m2 is m


def testAddUpdateAfterDeletionMovesToUpdates():
	m = Modifications(deletions=('/a.py',)).add_update('/a.py')
	assert '/a.py' in m.updates
	assert '/a.py' not in m.deletions


def testAddUpdatePreservesOtherEntries():
	m = Modifications(deletions=('/b.py',)).add_update('/a.py')
	assert '/b.py' in m.deletions
	assert '/a.py' in m.updates

#-------------------------------------------------------------------------------
# Modifications — __eq__ and __hash__

def testModificationsEqualWhenSameContent():
	a = Modifications(creations=('/a.py',), deletions=('/b.py',), updates=('/c.py',))
	b = Modifications(creations=('/a.py',), deletions=('/b.py',), updates=('/c.py',))
	assert a == b


def testModificationsNotEqualWhenDifferentContent():
	a = Modifications(creations=('/a.py',))
	b = Modifications(creations=('/b.py',))
	assert a != b


def testModificationsEqualityReturnsFalseForNonModifications():
	m = Modifications()
	assert m.__eq__('not a modifications') is NotImplemented


def testModificationsHashChangesWithContent():
	a = Modifications()
	b = a.add_creation('/a.py')
	assert hash(a) != hash(b)


def testModificationsEqualObjectsHaveSameHash():
	a = Modifications(creations=('/a.py',))
	b = Modifications(creations=('/a.py',))
	assert hash(a) == hash(b)

#-------------------------------------------------------------------------------
# SimulatedEvent

def testSimulatedEventAttributes():
	ev = SimulatedEvent('deleted', '/a.py')
	assert ev.event_type == 'deleted'
	assert ev.src_path == '/a.py'
	assert ev.is_directory is False

#-------------------------------------------------------------------------------
# PathMonitor — handle / event routing

def make_monitor():
	with patch('pavao.refresher.Observer'):
		return PathMonitor('/fake', MagicMock())


def make_event(event_type, src_path, is_directory=False):
	ev = MagicMock()
	ev.event_type = event_type
	ev.src_path = src_path
	ev.is_directory = is_directory
	return ev


def testHandleIgnoresDirectoryEvents():
	monitor = make_monitor()
	monitor.loop = MagicMock()

	with patch('pavao.refresher.asyncio.run_coroutine_threadsafe') as mock_rct:
		monitor.handle(make_event('created', '/fake/dir', is_directory=True))

	mock_rct.assert_not_called()


def testHandleIgnoresPycFiles():
	monitor = make_monitor()
	monitor.loop = MagicMock()

	with patch('pavao.refresher.asyncio.run_coroutine_threadsafe') as mock_rct:
		monitor.handle(make_event('modified', '/fake/module.pyc'))

	mock_rct.assert_not_called()


def testHandleSchedulesPythonFile():
	monitor = make_monitor()
	monitor.loop = MagicMock()

	def close_coro(coro, loop): coro.close(); return MagicMock()
	with patch('pavao.refresher.asyncio.run_coroutine_threadsafe', side_effect=close_coro) as mock_rct:
		monitor.handle(make_event('modified', '/fake/module.py'))

	mock_rct.assert_called_once()


def testOnCreatedDelegatesToHandle():
	monitor = make_monitor()
	monitor.handle = MagicMock()
	ev = make_event('created', '/fake/a.py')
	monitor.on_created(ev)
	monitor.handle.assert_called_once_with(ev)


def testOnDeletedDelegatesToHandle():
	monitor = make_monitor()
	monitor.handle = MagicMock()
	ev = make_event('deleted', '/fake/a.py')
	monitor.on_deleted(ev)
	monitor.handle.assert_called_once_with(ev)


def testOnModifiedDelegatesToHandle():
	monitor = make_monitor()
	monitor.handle = MagicMock()
	ev = make_event('modified', '/fake/a.py')
	monitor.on_modified(ev)
	monitor.handle.assert_called_once_with(ev)


def testOnMovedGeneratesDeleteThenCreate():
	monitor = make_monitor()
	handled = []
	monitor.handle = lambda ev: handled.append((ev.event_type, ev.src_path))

	ev = MagicMock()
	ev.is_directory = False
	ev.src_path = '/fake/old.py'
	ev.dest_path = '/fake/new.py'
	monitor.on_moved(ev)

	assert handled == [('deleted', '/fake/old.py'), ('created', '/fake/new.py')]


def testOnMovedIgnoresDirectoryMove():
	monitor = make_monitor()
	monitor.handle = MagicMock()

	ev = MagicMock()
	ev.is_directory = True
	monitor.on_moved(ev)

	monitor.handle.assert_not_called()

#-------------------------------------------------------------------------------
# PathMonitor — schedule_execution initialises primitives on the right loop

def testScheduleExecutionCreatesQueueAndEventOnGivenLoop():
	monitor = make_monitor()
	loop = asyncio.new_event_loop()

	try:
		with patch.object(monitor.observer, 'schedule'), \
			 patch.object(monitor.observer, 'start'):
			monitor.schedule_execution(loop)

		assert monitor.queue is not None
		assert monitor.changes is not None
		assert monitor.loop is loop
		assert monitor.running is True
	finally:
		monitor.monitoring.cancel()
		monitor.condensing.cancel()
		loop.run_until_complete(asyncio.sleep(0))
		loop.close()

#-------------------------------------------------------------------------------
# PathMonitor — _add_to_queue

@pytest.mark.asyncio
async def testAddToQueuePutsEventOnQueue():
	monitor = make_monitor()
	monitor.queue = asyncio.Queue()
	ev = make_event('created', '/fake/a.py')
	await monitor._add_to_queue(ev)
	assert monitor.queue.qsize() == 1
	assert await monitor.queue.get() is ev

#-------------------------------------------------------------------------------
# PathMonitor — _monitor coroutine

@pytest.mark.asyncio
async def testMonitorClassifiesCreatedEvent():
	monitor = make_monitor()
	monitor.queue = asyncio.Queue()
	monitor.changes = asyncio.Event()

	await monitor.queue.put(make_event('created', '/fake/a.py'))
	task = asyncio.create_task(monitor._monitor())
	await asyncio.sleep(0)
	task.cancel()
	try: await task
	except asyncio.CancelledError: pass

	assert '/fake/a.py' in monitor.modifications.creations


@pytest.mark.asyncio
async def testMonitorClassifiesModifiedEvent():
	monitor = make_monitor()
	monitor.queue = asyncio.Queue()
	monitor.changes = asyncio.Event()

	await monitor.queue.put(make_event('modified', '/fake/a.py'))
	task = asyncio.create_task(monitor._monitor())
	await asyncio.sleep(0)
	task.cancel()
	try: await task
	except asyncio.CancelledError: pass

	assert '/fake/a.py' in monitor.modifications.updates


@pytest.mark.asyncio
async def testMonitorClassifiesDeletedEvent():
	monitor = make_monitor()
	monitor.queue = asyncio.Queue()
	monitor.changes = asyncio.Event()

	await monitor.queue.put(make_event('deleted', '/fake/a.py'))
	task = asyncio.create_task(monitor._monitor())
	await asyncio.sleep(0)
	task.cancel()
	try: await task
	except asyncio.CancelledError: pass

	assert '/fake/a.py' in monitor.modifications.deletions


@pytest.mark.asyncio
async def testMonitorSetsChangesEventAfterProcessing():
	monitor = make_monitor()
	monitor.queue = asyncio.Queue()
	monitor.changes = asyncio.Event()

	await monitor.queue.put(make_event('created', '/fake/a.py'))
	task = asyncio.create_task(monitor._monitor())
	await asyncio.sleep(0)
	task.cancel()
	try: await task
	except asyncio.CancelledError: pass

	assert monitor.changes.is_set()


@pytest.mark.asyncio
async def testMonitorStopsCleanlyOnCancellation():
	monitor = make_monitor()
	monitor.queue = asyncio.Queue()
	monitor.changes = asyncio.Event()

	task = asyncio.create_task(monitor._monitor())
	await asyncio.sleep(0)
	task.cancel()
	await task  # should not raise

#-------------------------------------------------------------------------------
# PathMonitor — _collect coroutine

@pytest.mark.asyncio
async def testCollectFiresCallbackAfterDebounce():
	monitor = make_monitor()
	monitor.queue = asyncio.Queue()
	monitor.changes = asyncio.Event()
	monitor.modifications = Modifications(creations=('/a.py',))

	monitor.changes.set()

	task = asyncio.create_task(monitor._collect())
	await asyncio.sleep(1.1)
	task.cancel()
	try: await task
	except asyncio.CancelledError: pass

	monitor.callback.assert_called_once_with(('/a.py',), (), ())


@pytest.mark.asyncio
async def testCollectResetsModificationsAfterCallback():
	monitor = make_monitor()
	monitor.queue = asyncio.Queue()
	monitor.changes = asyncio.Event()
	monitor.modifications = Modifications(creations=('/a.py',))
	monitor.changes.set()

	task = asyncio.create_task(monitor._collect())
	await asyncio.sleep(1.1)
	task.cancel()
	try: await task
	except asyncio.CancelledError: pass

	assert monitor.modifications == Modifications()
	assert not monitor.changes.is_set()


@pytest.mark.asyncio
async def testCollectLogsAndContinuesAfterException():
	monitor = make_monitor()
	monitor.queue = asyncio.Queue()
	monitor.changes = asyncio.Event()

	call_count = []
	def bad_callback(*a):
		call_count.append(1)
		if len(call_count) == 1:
			raise RuntimeError("transient error")
	monitor.callback = bad_callback

	async def trigger_twice():
		for _ in range(2):
			monitor.modifications = Modifications(creations=('/a.py',))
			monitor.changes.set()
			await asyncio.sleep(1.1)

	task = asyncio.create_task(monitor._collect())
	with patch('pavao.refresher.Logger') as mock_logger:
		await trigger_twice()

	task.cancel()
	try: await task
	except asyncio.CancelledError: pass

	assert len(call_count) == 2
	mock_logger.warning.assert_called_once()


@pytest.mark.asyncio
async def testCollectStopsCleanlyOnCancellation():
	monitor = make_monitor()
	monitor.queue = asyncio.Queue()
	monitor.changes = asyncio.Event()

	task = asyncio.create_task(monitor._collect())
	await asyncio.sleep(0)
	task.cancel()
	await task  # should not raise


@pytest.mark.asyncio
async def testCollectDebounceLoopsWhenModificationsChange():
	monitor = make_monitor()
	monitor.queue = asyncio.Queue()
	monitor.changes = asyncio.Event()
	monitor.modifications = Modifications(creations=('/a.py',))
	monitor.changes.set()

	async def mutate_during_first_sleep():
		await asyncio.sleep(0.5)
		monitor.modifications = Modifications(creations=('/a.py', '/b.py'))

	task = asyncio.create_task(monitor._collect())
	mutate_task = asyncio.create_task(mutate_during_first_sleep())
	await asyncio.sleep(2.2)
	task.cancel()
	try: await task
	except asyncio.CancelledError: pass
	await mutate_task

	monitor.callback.assert_called_once_with(('/a.py', '/b.py'), (), ())

#-------------------------------------------------------------------------------
# PathMonitor — stop

def testStopCancelsTasksAndStopsObserver():
	monitor = make_monitor()
	monitor.running = True
	monitor.monitoring = MagicMock()
	monitor.condensing = MagicMock()

	with patch.object(monitor.observer, 'stop') as mock_stop, \
		 patch.object(monitor.observer, 'join') as mock_join:
		monitor.stop()

	assert monitor.running is False
	mock_stop.assert_called_once()
	mock_join.assert_called_once()
	monitor.monitoring.cancel.assert_called_once()
	monitor.condensing.cancel.assert_called_once()


def testStopIsIdempotentWhenNotRunning():
	monitor = make_monitor()
	monitor.running = False
	monitor.monitoring = MagicMock()

	monitor.stop()

	monitor.monitoring.cancel.assert_not_called()

#-------------------------------------------------------------------------------
# PathMonitor — _finish and stop_and_wait

@pytest.mark.asyncio
async def testFinishAwaitsMonitoringAndCondensing():
	monitor = make_monitor()

	async def noop(): pass

	monitor.monitoring = asyncio.ensure_future(noop())
	monitor.condensing = asyncio.ensure_future(noop())

	await monitor._finish()

	assert monitor.monitoring.done()
	assert monitor.condensing.done()


def testStopAndWaitStopsAndRunsUntilComplete():
	monitor = make_monitor()
	monitor.running = True
	monitor.monitoring = MagicMock()
	monitor.condensing = MagicMock()

	captured = []
	def capture_coro(coro):
		captured.append(coro)
		coro.close()

	mock_loop = MagicMock()
	mock_loop.run_until_complete.side_effect = capture_coro
	monitor.loop = mock_loop

	with patch.object(monitor.observer, 'stop'), \
		 patch.object(monitor.observer, 'join'):
		monitor.stop_and_wait()

	assert monitor.running is False
	mock_loop.run_until_complete.assert_called_once()

#-------------------------------------------------------------------------------

if __name__ == "__main__":
	pytest.main([__file__, "-v"])
