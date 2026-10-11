
import sys
sys.path.append('..')

import asyncio
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, AsyncMock, patch
from pavao.daemon import Daemon

#-------------------------------------------------------------------------------

def make_task(source, enabled=True):
	task = MagicMock()
	task.source = source
	task.enabled = enabled
	task.execution = None
	task.run = MagicMock()
	task.cancel_if_executing = MagicMock(return_value=True)
	return task

@pytest.fixture
def loop():
	try:
		return asyncio.get_running_loop()
	except RuntimeError:
		loop = asyncio.new_event_loop()
		asyncio.set_event_loop(loop)
		return loop

@pytest.fixture
def broadcaster():
	return MagicMock()

@pytest.fixture
def daemon(broadcaster):
	loop = asyncio.new_event_loop()
	asyncio.set_event_loop(loop)
	d = Daemon(loop, broadcaster)
	d.internal_db = AsyncMock()
	return d

@pytest.fixture
async def async_daemon(broadcaster):
	loop = asyncio.get_running_loop()
	d = Daemon(loop, broadcaster)
	d.internal_db = AsyncMock()
	return d

#-------------------------------------------------------------------------------
# initial state

def testInitialState(daemon):
	assert daemon.active is False
	assert daemon.restarter is None
	assert daemon.enabled_services == set()
	assert daemon.finished_services == dict()

#-------------------------------------------------------------------------------
# get_base_context

def testGetBaseContextContainsBroadcasting(daemon):
	assert 'broadcasting' in daemon.get_base_context()

def testGetBaseContextContainsOnFinish(daemon):
	assert 'on_finish' in daemon.get_base_context()

#-------------------------------------------------------------------------------
# start_task

def testStartTaskCallsRun(daemon):
	task = make_task("svc.py")
	daemon.start_task(task)
	task.run.assert_called_once()

def testStartTaskPassesBroadcasterInContext(daemon, broadcaster):
	task = make_task("svc.py")
	daemon.start_task(task)
	_, _, _, context, _, _ = task.run.call_args.args
	assert context['broadcasting'] is broadcaster

def testStartTaskProvidesOnFinishCallback(daemon):
	task = make_task("svc.py")
	daemon.start_task(task)
	_, _, _, context, _, _ = task.run.call_args.args
	assert callable(context['on_finish'])

@pytest.mark.asyncio
async def testStartTaskOnOutputBroadcastsMessage(daemon, broadcaster):
	task = make_task("svc.py")
	task.ident = 5
	daemon.start_task(task)
	_, _, _, _, on_output, _ = task.run.call_args.args
	broadcaster.write_message = AsyncMock()
	await on_output(task, "some output")
	broadcaster.write_message.assert_called_once_with("taskState:5", "OUTPUT:some output")


@pytest.mark.asyncio
async def testStartTaskOnFinishRecordsTermination(daemon):
	task = make_task("svc.py")
	daemon.start_task(task)
	_, _, _, _, _, on_finish = task.run.call_args.args
	await on_finish(task.source, 1, True)
	assert "svc.py" in daemon.finished_services

@pytest.mark.asyncio
async def testStartTaskOnFinishLogsWhenActive(daemon):
	task = make_task("svc.py")
	daemon.active = True
	daemon.start_task(task)
	_, _, _, _, _, on_finish = task.run.call_args.args
	with patch('pavao.daemon.Logger') as mock_logger:
		await on_finish(task.source, 1, True)
		mock_logger.info.assert_called_once()

@pytest.mark.asyncio
async def testStartTaskOnFinishSilentWhenInactive(daemon):
	task = make_task("svc.py")
	daemon.active = False
	daemon.start_task(task)
	_, _, _, _, _, on_finish = task.run.call_args.args
	with patch('pavao.daemon.Logger') as mock_logger:
		await on_finish(task.source, 1, True)
		mock_logger.info.assert_not_called()

@pytest.mark.asyncio
async def testStartTaskFinishCallbacksInvoked(daemon):
	called = []
	task = make_task("svc.py")
	daemon.start_task(task)
	_, _, _, context, _, on_finish = task.run.call_args.args
	context['on_finish'](lambda: called.append(True))
	await on_finish(task.source, 1, True)
	assert called == [True]

#-------------------------------------------------------------------------------
# execute_tasks

@pytest.mark.asyncio
async def testExecuteTasksSetsActive(daemon):
	await daemon.execute_tasks()
	assert daemon.active is True

@pytest.mark.asyncio
async def testExecuteTasksStartsEnabledTasks(broadcaster):
	d = Daemon(asyncio.get_running_loop(), broadcaster)
	d.internal_db = AsyncMock()
	t1 = make_task("a.py", enabled=True)
	t2 = make_task("b.py", enabled=True)
	d.loaded_tasks = [t1, t2]
	await d.execute_tasks()
	t1.run.assert_called_once()
	t2.run.assert_called_once()
	d.restarter.cancel()
	await asyncio.sleep(0)

@pytest.mark.asyncio
async def testExecuteTasksSkipsDisabledTasks(daemon):
	t = make_task("a.py", enabled=False)
	daemon.loaded_tasks = [t]
	await daemon.execute_tasks()
	t.run.assert_not_called()

@pytest.mark.asyncio
async def testExecuteTasksAddsToEnabledServices(broadcaster):
	d = Daemon(asyncio.get_running_loop(), broadcaster)
	d.internal_db = AsyncMock()
	t = make_task("a.py", enabled=True)
	d.loaded_tasks = [t]
	await d.execute_tasks()
	assert "a.py" in d.enabled_services
	d.restarter.cancel()
	await asyncio.sleep(0)

@pytest.mark.asyncio
async def testExecuteTasksCreatesRestarter(broadcaster):
	d = Daemon(asyncio.get_running_loop(), broadcaster)
	d.internal_db = AsyncMock()
	t = make_task("a.py", enabled=True)
	d.loaded_tasks = [t]
	await d.execute_tasks()
	assert d.restarter is not None
	await asyncio.sleep(0)  # let restarter enter its first sleep
	d.restarter.cancel()
	await asyncio.sleep(0)  # let cancel propagate

@pytest.mark.asyncio
async def testExecuteTasksNoRestarterWhenNoTasks(daemon):
	daemon.loaded_tasks = []
	await daemon.execute_tasks()
	assert daemon.restarter is None

#-------------------------------------------------------------------------------
# stop_module / start_module

def testStopModuleRemovesFromEnabled(daemon):
	t = make_task("svc.py")
	daemon.loaded_tasks = [t]
	daemon.enabled_services.add("svc.py")
	daemon.stop_module("svc.py")
	assert "svc.py" not in daemon.enabled_services

def testStopModuleCancelsTask(daemon):
	t = make_task("svc.py")
	daemon.loaded_tasks = [t]
	daemon.enabled_services.add("svc.py")
	daemon.stop_module("svc.py")
	t.cancel_if_executing.assert_called_once()

def testStopModuleUnknownSourceDoesNothing(daemon):
	daemon.loaded_tasks = []
	daemon.stop_module("nonexistent.py")  # must not raise

def testStartModuleAddsToEnabled(daemon):
	t = make_task("svc.py")
	daemon.loaded_tasks = [t]
	daemon.start_module("svc.py")
	assert "svc.py" in daemon.enabled_services

def testStartModuleCallsRun(daemon):
	t = make_task("svc.py")
	daemon.loaded_tasks = [t]
	daemon.start_module("svc.py")
	t.run.assert_called_once()

def testStartModuleIdempotent(daemon):
	t = make_task("svc.py")
	daemon.loaded_tasks = [t]
	daemon.enabled_services.add("svc.py")
	daemon.start_module("svc.py")
	t.run.assert_not_called()

def testStartModuleUnknownSourceDoesNothing(daemon):
	daemon.loaded_tasks = []
	daemon.start_module("nonexistent.py")  # must not raise

#-------------------------------------------------------------------------------
# restart_services

@pytest.mark.asyncio
async def testRestartServicesRestartsAfterDelay(daemon):
	t = make_task("svc.py")
	daemon.loaded_tasks = [t]
	daemon.enabled_services.add("svc.py")
	old_time = datetime.now(timezone.utc) - timedelta(seconds=10)
	daemon.finished_services["svc.py"] = old_time

	sleep_count = 0
	async def fake_sleep(secs):
		nonlocal sleep_count
		sleep_count += 1
		if sleep_count >= 2:
			daemon.active = False  # stop after first full iteration

	with patch('pavao.daemon.asyncio.sleep', side_effect=fake_sleep):
		daemon.active = True
		await daemon.restart_services()

	t.run.assert_called_once()

@pytest.mark.asyncio
async def testRestartServicesRetainsRecentlyFinished(daemon):
	t = make_task("svc.py")
	daemon.loaded_tasks = [t]
	daemon.enabled_services.add("svc.py")
	recent_time = datetime.now(timezone.utc) - timedelta(seconds=1)
	daemon.finished_services["svc.py"] = recent_time

	sleep_count = 0
	async def fake_sleep(secs):
		nonlocal sleep_count
		sleep_count += 1
		if sleep_count >= 2:
			daemon.active = False

	with patch('pavao.daemon.asyncio.sleep', side_effect=fake_sleep):
		daemon.active = True
		await daemon.restart_services()

	t.run.assert_not_called()
	assert "svc.py" in daemon.finished_services

@pytest.mark.asyncio
async def testRestartServicesIgnoresStoppedServices(daemon):
	t = make_task("svc.py")
	daemon.loaded_tasks = [t]
	# not in enabled_services
	old_time = datetime.now(timezone.utc) - timedelta(seconds=10)
	daemon.finished_services["svc.py"] = old_time

	async def fake_sleep(secs):
		daemon.active = False

	with patch('pavao.daemon.asyncio.sleep', side_effect=fake_sleep):
		daemon.active = True
		await daemon.restart_services()

	t.run.assert_not_called()

#-------------------------------------------------------------------------------
# stop

@pytest.mark.asyncio
async def testStopSetsActiveToFalse(daemon):
	daemon.active = True
	await daemon.stop()
	assert daemon.active is False

@pytest.mark.asyncio
async def testStopCancelsRestarter(daemon):
	restarter = MagicMock()
	daemon.restarter = restarter
	await daemon.stop()
	restarter.cancel.assert_called_once()
	assert daemon.restarter is None

@pytest.mark.asyncio
async def testStopClearsEnabledServices(daemon):
	daemon.enabled_services = {"a.py", "b.py"}
	await daemon.stop()
	assert daemon.enabled_services == set()

@pytest.mark.asyncio
async def testStopClearsFinishedServices(daemon):
	daemon.finished_services = {"a.py": datetime.now(timezone.utc)}
	await daemon.stop()
	assert daemon.finished_services == {}

@pytest.mark.asyncio
async def testStopAwaitsRunningTasks(daemon):
	loop = asyncio.get_running_loop()

	async def long_running():
		try:
			await asyncio.sleep(100)
		except asyncio.CancelledError:
			pass

	t = make_task("svc.py")
	execution = loop.create_task(long_running())
	t.execution = execution
	daemon.loaded_tasks = [t]
	daemon.executor = loop.create_task(asyncio.sleep(0))
	await asyncio.sleep(0)

	await daemon.stop()
	assert execution.cancelled() or execution.done()

#-------------------------------------------------------------------------------

if __name__ == "__main__":
	pytest.main([__file__, "-v"])
