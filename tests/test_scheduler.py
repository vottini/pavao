
import sys
sys.path.append('..')

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock, patch
from pavao.scheduler import Scheduler, SchedulableTask, wait_whole_minute
from pavao.task import TaskException, TaskProblem, Task

#-------------------------------------------------------------------------------
# helpers

EVERY_MINUTE = "* * * * *"

async def _noop_processor():
	yield "output"

async def _slow_processor():
	await asyncio.sleep(100)
	yield

def make_task(schedule=EVERY_MINUTE, name="t"):
	return SchedulableTask("svc.py", {
		'processor': _noop_processor,
		'name': name,
		'schedule': schedule,
	})

def make_db():
	cursor = AsyncMock()
	cursor.execute = AsyncMock(return_value=cursor)
	cursor.fetchone = AsyncMock(return_value=(1, True))
	cursor.__aenter__ = AsyncMock(return_value=cursor)
	cursor.__aexit__ = AsyncMock(return_value=None)
	db = AsyncMock()
	db.cursor = MagicMock(return_value=cursor)
	db.commit = AsyncMock()
	return db

@pytest.fixture(autouse=True)
def reset_ident_counter():
	original = Task.ident_counter
	yield
	Task.ident_counter = original

@pytest.fixture
def broadcaster():
	b = AsyncMock()
	b.write_message = AsyncMock()
	return b

@pytest.fixture
def scheduler(broadcaster):
	loop = asyncio.new_event_loop()
	s = Scheduler(loop, broadcaster)
	s.internal_db = make_db()
	return s

#-------------------------------------------------------------------------------
# SchedulableTask.__init__

def testSchedulableTaskSetsSchedule():
	t = make_task(schedule=EVERY_MINUTE)
	assert t.schedule == EVERY_MINUTE

def testSchedulableTaskInitialOutputEmpty():
	assert make_task().get_output() == []

def testSchedulableTaskNextExecutionInitiallyNone():
	assert make_task().next_execution is None

def testSchedulableTaskSchedulerInitiallyNone():
	assert make_task().scheduler is None

#-------------------------------------------------------------------------------
# output management

def testAppendOutputConvertsToString():
	t = make_task()
	t.append_output(42)
	assert t.get_output() == ["42"]

def testGetOutputReturnsACopy():
	t = make_task()
	t.append_output("x")
	copy = t.get_output()
	copy.append("y")
	assert t.get_output() == ["x"]

def testClearOutputEmptiesList():
	t = make_task()
	t.append_output("x")
	t.clear_output()
	assert t.get_output() == []

#-------------------------------------------------------------------------------
# enable / disable

@pytest.mark.asyncio
async def testEnableSetsNextExecution():
	t = make_task()
	await t.enable()
	assert t.next_execution is not None

@pytest.mark.asyncio
async def testEnableNextExecutionIsInFuture():
	t = make_task()
	await t.enable()
	assert t.next_execution > datetime.now()

@pytest.mark.asyncio
async def testEnableSetsEnabledTrue():
	t = make_task()
	await t.disable()
	await t.enable()
	assert t.enabled is True

@pytest.mark.asyncio
async def testEnableBroadcastsWhenBroadcasterProvided(broadcaster):
	t = make_task()
	await t.enable(broadcaster=broadcaster)
	broadcaster.write_message.assert_called_once()
	topic, msg = broadcaster.write_message.call_args.args
	assert topic == f"taskState:{t.ident}"
	assert msg.startswith("ENABLED:")

@pytest.mark.asyncio
async def testEnableNoBroadcastWhenNoBroadcaster():
	t = make_task()
	await t.enable(broadcaster=None)  # must not raise

@pytest.mark.asyncio
async def testDisableSetsEnabledFalse():
	t = make_task()
	await t.disable()
	assert t.enabled is False

@pytest.mark.asyncio
async def testDisableClearsNextExecution():
	t = make_task()
	await t.enable()
	await t.disable()
	assert t.next_execution is None

@pytest.mark.asyncio
async def testDisableClearsScheduler():
	t = make_task()
	await t.enable()
	await t.disable()
	assert t.scheduler is None

@pytest.mark.asyncio
async def testDisableBroadcastsWhenBroadcasterProvided(broadcaster):
	t = make_task()
	await t.disable(broadcaster=broadcaster)
	broadcaster.write_message.assert_called_once()
	topic, msg = broadcaster.write_message.call_args.args
	assert topic == f"taskState:{t.ident}"
	assert msg == "DISABLED"

#-------------------------------------------------------------------------------
# step_schedule / lateness

@pytest.mark.asyncio
async def testStepScheduleAdvancesNextExecution():
	t = make_task()
	await t.enable()
	first = t.next_execution
	t.step_schedule()
	assert t.next_execution > first

@pytest.mark.asyncio
async def testLatenessReturnsZeroWhenNotLate():
	t = make_task()
	await t.enable()
	assert t.lateness() == timedelta()

@pytest.mark.asyncio
async def testLatenessRaisesWhenDisabled():
	t = make_task()
	await t.disable()
	with pytest.raises(TaskException):
		t.lateness()

@pytest.mark.asyncio
async def testLatenessReturnsPositiveDeltaWhenLate():
	t = make_task()
	await t.enable()
	t.next_execution = datetime.now() - timedelta(minutes=5)
	assert t.lateness() > timedelta()

#-------------------------------------------------------------------------------
# wait_whole_minute

@pytest.mark.asyncio
async def testWaitWholeMinuteSleepsUntilNextMinute():
	slept = []
	async def fake_sleep(secs): slept.append(secs)
	with patch('pavao.scheduler.asyncio.sleep', side_effect=fake_sleep):
		with patch('pavao.scheduler.datetime') as mock_dt:
			fixed = datetime(2024, 1, 1, 12, 0, 30, 500000)
			mock_dt.now.return_value = fixed
			mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
			await wait_whole_minute()
	assert len(slept) == 1
	assert abs(slept[0] - 29.5) < 0.01

@pytest.mark.asyncio
async def testWaitWholeMinuteRecursesAfterSuspension():
	call_count = 0
	times = [
		datetime(2024, 1, 1, 12, 0, 0, 0),    # start of first call
		datetime(2024, 1, 1, 12, 5, 0, 0),    # end of first call (5 min later - suspended)
		datetime(2024, 1, 1, 12, 5, 0, 0),    # start of recursive call
		datetime(2024, 1, 1, 12, 6, 0, 0),    # end of recursive call (normal)
	]

	async def fake_sleep(secs): pass

	with patch('pavao.scheduler.asyncio.sleep', side_effect=fake_sleep):
		with patch('pavao.scheduler.datetime') as mock_dt:
			mock_dt.now.side_effect = times
			mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
			await wait_whole_minute()

	assert mock_dt.now.call_count == 4

#-------------------------------------------------------------------------------
# Scheduler.get_base_context

def testGetBaseContextContainsBroadcasting(scheduler):
	assert 'broadcasting' in scheduler.get_base_context()

#-------------------------------------------------------------------------------
# Scheduler.start_task

def testStartTaskCallsRun(scheduler):
	t = MagicMock()
	t.run = MagicMock()
	scheduler.start_task(t)
	t.run.assert_called_once()

def testStartTaskPassesBroadcasterInContext(scheduler, broadcaster):
	t = MagicMock()
	t.run = MagicMock()
	scheduler.start_task(t)
	_, _, _, context, _, _ = t.run.call_args.args
	assert context['broadcasting'] is broadcaster

@pytest.mark.asyncio
async def testStartTaskOnOutputAppendsToTask(scheduler):
	t = MagicMock()
	t.run = MagicMock()
	scheduler.start_task(t)
	_, _, _, _, on_output, _ = t.run.call_args.args
	await on_output(t, "hello")
	t.append_output.assert_called_once_with("hello")

@pytest.mark.asyncio
async def testStartTaskOnFinishClearsOutput(scheduler):
	t = MagicMock()
	t.run = MagicMock()
	scheduler.start_task(t)
	_, _, _, _, _, on_finish = t.run.call_args.args
	await on_finish(t.ident, 1, True)
	t.clear_output.assert_called_once()

#-------------------------------------------------------------------------------
# Scheduler._verify_task

def testVerifyTaskNotFoundWhenNone(scheduler):
	assert scheduler._verify_task(None, True) == TaskProblem.NOT_FOUND

def testVerifyTaskNotInExecutionWhenNoExecution(scheduler):
	t = MagicMock()
	t.execution = None
	assert scheduler._verify_task(t, should_be_running=True) == TaskProblem.NOT_IN_EXECUTION

def testVerifyTaskInExecutionWhenRunning(scheduler):
	t = MagicMock()
	t.execution = MagicMock()
	assert scheduler._verify_task(t, should_be_running=False) == TaskProblem.IN_EXECUTION

def testVerifyTaskNoneWhenIdleAndExpectingIdle(scheduler):
	t = MagicMock()
	t.execution = None
	assert scheduler._verify_task(t, should_be_running=False) == TaskProblem.NONE

def testVerifyTaskNoneWhenRunningAndExpectingRunning(scheduler):
	t = MagicMock()
	t.execution = MagicMock()
	assert scheduler._verify_task(t, should_be_running=True) == TaskProblem.NONE

#-------------------------------------------------------------------------------
# Scheduler.run_task / cancel_task

def testRunTaskReturnsTrueOnSuccess(scheduler):
	t = MagicMock()
	t.execution = None
	scheduler.loaded_tasks = [t]
	ok, problem = scheduler.run_task(t.ident)
	assert ok is True and problem == TaskProblem.NONE

def testRunTaskReturnsFalseWhenAlreadyRunning(scheduler):
	t = MagicMock()
	t.execution = MagicMock()
	scheduler.loaded_tasks = [t]
	ok, problem = scheduler.run_task(t.ident)
	assert ok is False and problem == TaskProblem.IN_EXECUTION

def testRunTaskReturnsFalseWhenNotFound(scheduler):
	scheduler.loaded_tasks = []
	ok, problem = scheduler.run_task(999)
	assert ok is False and problem == TaskProblem.NOT_FOUND

def testCancelTaskReturnsTrueOnSuccess(scheduler):
	t = MagicMock()
	t.execution = MagicMock()
	scheduler.loaded_tasks = [t]
	ok, problem = scheduler.cancel_task(t.ident)
	assert ok is True and problem == TaskProblem.NONE
	t.cancel_if_executing.assert_called_once()

def testCancelTaskReturnsFalseWhenNotRunning(scheduler):
	t = MagicMock()
	t.execution = None
	scheduler.loaded_tasks = [t]
	ok, problem = scheduler.cancel_task(t.ident)
	assert ok is False and problem == TaskProblem.NOT_IN_EXECUTION

def testCancelTaskReturnsFalseWhenNotFound(scheduler):
	scheduler.loaded_tasks = []
	ok, problem = scheduler.cancel_task(999)
	assert ok is False and problem == TaskProblem.NOT_FOUND

#-------------------------------------------------------------------------------
# Scheduler.execute_tasks

@pytest.mark.asyncio
async def testExecuteTasksStartsDueTask(broadcaster):
	s = Scheduler(asyncio.get_running_loop(), broadcaster)
	s.internal_db = make_db()
	t = MagicMock()
	t.enabled = True
	t.execution = None
	t.next_execution = datetime.now() - timedelta(seconds=1)
	t.lateness.return_value = timedelta()
	s.loaded_tasks = [t]

	sleep_count = 0
	async def fake_sleep(secs):
		nonlocal sleep_count
		sleep_count += 1
		if sleep_count >= 2:
			s.loaded_tasks = []

	with patch('pavao.scheduler.asyncio.sleep', side_effect=fake_sleep):
		with patch('pavao.scheduler.datetime') as mock_dt:
			mock_dt.now.return_value = datetime.now()
			mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
			await s.execute_tasks()

	t.run.assert_called_once()

@pytest.mark.asyncio
async def testExecuteTasksSkipsDisabledTask(broadcaster):
	s = Scheduler(asyncio.get_running_loop(), broadcaster)
	s.internal_db = make_db()
	t = MagicMock()
	t.enabled = False
	s.loaded_tasks = [t]

	sleep_count = 0
	async def fake_sleep(secs):
		nonlocal sleep_count
		sleep_count += 1
		if sleep_count >= 2:
			s.loaded_tasks = []

	with patch('pavao.scheduler.asyncio.sleep', side_effect=fake_sleep):
		with patch('pavao.scheduler.datetime') as mock_dt:
			mock_dt.now.return_value = datetime.now()
			mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
			await s.execute_tasks()

	t.run.assert_not_called()

@pytest.mark.asyncio
async def testExecuteTasksSkipsTaskNotYetDue(broadcaster):
	s = Scheduler(asyncio.get_running_loop(), broadcaster)
	s.internal_db = make_db()
	t = MagicMock()
	t.enabled = True
	t.next_execution = datetime.now() + timedelta(hours=1)
	s.loaded_tasks = [t]

	async def fake_sleep(secs):
		s.loaded_tasks = []

	with patch('pavao.scheduler.asyncio.sleep', side_effect=fake_sleep):
		with patch('pavao.scheduler.datetime') as mock_dt:
			mock_dt.now.return_value = datetime.now()
			mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
			await s.execute_tasks()

	t.run.assert_not_called()

@pytest.mark.asyncio
async def testExecuteTasksSkipsLateTasksBeyondThreshold(broadcaster):
	s = Scheduler(asyncio.get_running_loop(), broadcaster)
	s.internal_db = make_db()
	t = MagicMock()
	t.enabled = True
	t.next_execution = datetime.now() - timedelta(minutes=5)
	# First call (inside the while): above threshold; second call: below, so the
	# loop exits after one step_schedule() call instead of spinning forever.
	t.lateness.side_effect = [timedelta(minutes=5), timedelta()]
	def advance_next():
		t.next_execution = datetime.now() + timedelta(hours=1)
	t.step_schedule.side_effect = advance_next
	s.loaded_tasks = [t]

	sleep_count = 0
	async def fake_sleep(secs):
		nonlocal sleep_count
		sleep_count += 1
		if sleep_count >= 2:
			s.loaded_tasks = []

	with patch('pavao.scheduler.asyncio.sleep', side_effect=fake_sleep):
		with patch('pavao.scheduler.datetime') as mock_dt:
			mock_dt.now.return_value = datetime.now()
			mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
			await s.execute_tasks()

	t.step_schedule.assert_called()
	t.run.assert_not_called()

@pytest.mark.asyncio
async def testExecuteTasksSkipsAlreadyRunningTask(broadcaster):
	s = Scheduler(asyncio.get_running_loop(), broadcaster)
	s.internal_db = make_db()
	t = MagicMock()
	t.enabled = True
	t.next_execution = datetime.now() - timedelta(seconds=1)
	t.lateness.return_value = timedelta()
	t.execution = MagicMock()  # task is already running
	s.loaded_tasks = [t]

	sleep_count = 0
	async def fake_sleep(secs):
		nonlocal sleep_count
		sleep_count += 1
		if sleep_count >= 2:
			s.loaded_tasks = []

	with patch('pavao.scheduler.asyncio.sleep', side_effect=fake_sleep):
		with patch('pavao.scheduler.datetime') as mock_dt:
			mock_dt.now.return_value = datetime.now()
			mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
			await s.execute_tasks()

	t.run.assert_not_called()
	t.step_schedule.assert_called()

#-------------------------------------------------------------------------------
# Scheduler.stop

@pytest.mark.asyncio
async def testStopCancelsExecutor(scheduler):
	loop = asyncio.get_running_loop()
	future = loop.create_future()
	future.set_result(None)
	cancel_spy = MagicMock(return_value=False)
	future.cancel = cancel_spy
	scheduler.executor = future
	await scheduler.stop()
	cancel_spy.assert_called_once()
	assert scheduler.executor is None

@pytest.mark.asyncio
async def testStopCancelsRunningTasks(scheduler):
	loop = asyncio.get_running_loop()

	async def long_running():
		try:
			await asyncio.sleep(100)
		except asyncio.CancelledError:
			pass

	t = MagicMock()
	execution = loop.create_task(long_running())
	t.execution = execution
	scheduler.loaded_tasks = [t]
	scheduler.executor = loop.create_task(asyncio.sleep(0))
	await asyncio.sleep(0)

	await scheduler.stop()
	assert execution.cancelled() or execution.done()

@pytest.mark.asyncio
async def testStopAbsorbsCancelledErrorFromTask(scheduler):
	loop = asyncio.get_running_loop()

	async def unchecked():
		await asyncio.sleep(100)

	t = MagicMock()
	t.execution = loop.create_task(unchecked())
	scheduler.loaded_tasks = [t]
	scheduler.executor = loop.create_future()
	scheduler.executor.set_result(None)

	await scheduler.stop()  # must not raise despite CancelledError from task

@pytest.mark.asyncio
async def testStopAbsorbsCancelledErrorFromExecutor(scheduler):
	loop = asyncio.get_running_loop()

	async def unchecked():
		await asyncio.sleep(100)

	scheduler.executor = loop.create_task(unchecked())

	await scheduler.stop()  # must not raise despite CancelledError from executor

@pytest.mark.asyncio
async def testStopNoOpWhenNoExecutor(scheduler):
	scheduler.executor = None
	await scheduler.stop()  # must not raise

#-------------------------------------------------------------------------------

if __name__ == "__main__":
	pytest.main([__file__, "-v"])
