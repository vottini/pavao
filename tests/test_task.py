
import sys
sys.path.append('..')

import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock
from pavao.task import Task, TaskManager, TaskException, TaskProblem, get_identity
from pavao.i18n import LazyLocalizer

#-------------------------------------------------------------------------------
# helpers

async def _noop_processor():
	yield "output"

async def _empty_processor():
	return
	yield

async def _error_processor():
	raise ValueError("boom")
	yield

async def _multi_processor():
	yield "first"
	yield "second"

async def _slow_processor():
	await asyncio.sleep(100)
	yield "never"

def make_task(processor=_noop_processor, name="test_task", source="task.py"):
	return Task(source, {'processor': processor, 'name': name})

def make_db():
	cursor = AsyncMock()
	cursor.execute = AsyncMock(return_value=cursor)
	cursor.fetchone = AsyncMock(return_value=(42, True))
	cursor.__aenter__ = AsyncMock(return_value=cursor)
	cursor.__aexit__ = AsyncMock(return_value=None)
	db = AsyncMock()
	db.cursor = MagicMock(return_value=cursor)
	db.commit = AsyncMock()
	return db, cursor

def make_broadcaster():
	b = AsyncMock()
	b.write_message = AsyncMock()
	return b

async def _run_and_await(t, db, b, on_output=None, on_finish=None):
	loop = asyncio.get_running_loop()
	t.run(loop, b, db, {}, on_output or AsyncMock(), on_finish)
	execution = t.execution
	await execution
	return execution

@pytest.fixture(autouse=True)
def reset_ident_counter():
	original = Task.ident_counter
	yield
	Task.ident_counter = original

#-------------------------------------------------------------------------------
# get_identity

def testGetIdentityPassesThrough():
	assert get_identity("plain") == "plain"
	assert get_identity(42) == 42

def testGetIdentityCallsLazyLocalizer():
	ll = MagicMock(spec=LazyLocalizer)
	ll.identity.return_value = "module::key"
	assert get_identity(ll) == "module::key"

#-------------------------------------------------------------------------------
# Task.__init__

def testTaskRequiresAsyncGenerator():
	async def not_a_gen(): pass
	with pytest.raises(TaskException):
		Task("src.py", {'processor': not_a_gen, 'name': 'x'})

def testTaskRejectsNonAsync():
	def sync_gen():
		yield 1
	with pytest.raises(TaskException):
		Task("src.py", {'processor': sync_gen, 'name': 'x'})

def testTaskInitSetsSource():
	t = make_task()
	assert t.source == "task.py"

def testTaskInitSetsName():
	t = make_task(name="my_task")
	assert t.name == "my_task"

def testTaskInitEnabledByDefault():
	t = make_task()
	assert t.enabled is True

def testTaskInitExecutionIsNone():
	t = make_task()
	assert t.execution is None

def testTaskInitPrePostProcessingNone():
	t = make_task()
	assert t.pre_processing is None
	assert t.post_processing is None

def testTaskGeneratesUniqueIdents():
	t1 = make_task()
	t2 = make_task()
	assert t1.ident != t2.ident

#-------------------------------------------------------------------------------
# enable / disable

@pytest.mark.asyncio
async def testTaskEnable():
	t = make_task()
	t.enabled = False
	await t.enable()
	assert t.enabled is True

@pytest.mark.asyncio
async def testTaskDisable():
	t = make_task()
	await t.disable()
	assert t.enabled is False

#-------------------------------------------------------------------------------
# localized_package / localized_name

def testLocalizedPackagePlain():
	t = make_task()
	t.package = "mypkg"
	assert t.localized_package([]) == "mypkg"

def testLocalizedNamePlain():
	t = make_task()
	assert t.localized_name([]) == "test_task"

def testLocalizedPackageLazyLocalizer():
	t = make_task()
	ll = MagicMock(spec=LazyLocalizer)
	ll.localize.return_value = "My Package"
	t.package = ll
	assert t.localized_package(["en_US"]) == "My Package"
	ll.localize.assert_called_with(["en_US"])

def testLocalizedNameLazyLocalizer():
	t = make_task()
	ll = MagicMock(spec=LazyLocalizer)
	ll.localize.return_value = "My Task"
	t.name = ll
	assert t.localized_name(["en_US"]) == "My Task"

#-------------------------------------------------------------------------------
# cancel_if_executing

def testCancelIfExecutingReturnsFalseWhenIdle():
	t = make_task()
	assert t.cancel_if_executing() is False

def testCancelIfExecutingCancelsAndReturnsTrue():
	t = make_task()
	t.execution = MagicMock()
	assert t.cancel_if_executing() is True
	t.execution.cancel.assert_called_once()

def testCancelIfExecutingDoesNotNullExecution():
	t = make_task()
	mock_exec = MagicMock()
	t.execution = mock_exec
	t.cancel_if_executing()
	assert t.execution is mock_exec

#-------------------------------------------------------------------------------
# run / create_future — happy path

@pytest.mark.asyncio
async def testRunBroadcastsStarted():
	t = make_task()
	db, cursor = make_db()
	b = make_broadcaster()
	await _run_and_await(t, db, b)
	b.write_message.assert_any_call(f"taskState:{t.ident}", "STARTED")

@pytest.mark.asyncio
async def testRunBroadcastsFinished():
	t = make_task()
	db, cursor = make_db()
	b = make_broadcaster()
	await _run_and_await(t, db, b)
	b.write_message.assert_any_call(f"taskState:{t.ident}", "FINISHED")

@pytest.mark.asyncio
async def testRunCallsOnOutput():
	t = make_task()
	db, cursor = make_db()
	b = make_broadcaster()
	on_output = AsyncMock()
	await _run_and_await(t, db, b, on_output=on_output)
	on_output.assert_called_once()

@pytest.mark.asyncio
async def testRunCallsOnFinishWithSuccess():
	t = make_task()
	db, cursor = make_db()
	b = make_broadcaster()
	on_finish = AsyncMock()
	await _run_and_await(t, db, b, on_finish=on_finish)
	_, _, success = on_finish.call_args.args
	assert success is True

@pytest.mark.asyncio
async def testRunCommitsDb():
	t = make_task()
	db, cursor = make_db()
	b = make_broadcaster()
	await _run_and_await(t, db, b)
	assert db.commit.call_count >= 2

@pytest.mark.asyncio
async def testRunClearsExecutionAfterFinish():
	t = make_task()
	db, cursor = make_db()
	b = make_broadcaster()
	await _run_and_await(t, db, b)
	assert t.execution is None

@pytest.mark.asyncio
async def testRunMultipleOutputs():
	t = make_task(processor=_multi_processor)
	db, cursor = make_db()
	b = make_broadcaster()
	on_output = AsyncMock()
	await _run_and_await(t, db, b, on_output=on_output)
	assert on_output.call_count == 2

@pytest.mark.asyncio
async def testRunEmptyProcessorNoOutput():
	t = make_task(processor=_empty_processor)
	db, cursor = make_db()
	b = make_broadcaster()
	on_output = AsyncMock()
	await _run_and_await(t, db, b, on_output=on_output)
	on_output.assert_not_called()

#-------------------------------------------------------------------------------
# run — exception handling

@pytest.mark.asyncio
async def testRunOnExceptionCallsOnFinishWithFailure():
	t = make_task(processor=_error_processor)
	db, cursor = make_db()
	b = make_broadcaster()
	on_finish = AsyncMock()
	await _run_and_await(t, db, b, on_finish=on_finish)
	_, _, success = on_finish.call_args.args
	assert success is False

@pytest.mark.asyncio
async def testRunOnExceptionLogsOutput():
	t = make_task(processor=_error_processor)
	db, cursor = make_db()
	b = make_broadcaster()
	on_output = AsyncMock()
	await _run_and_await(t, db, b, on_output=on_output)
	on_output.assert_called_once()

@pytest.mark.asyncio
async def testRunOnCancelledCallsOnFinishWithFailure():
	t = make_task(processor=_slow_processor)
	db, cursor = make_db()
	b = make_broadcaster()
	on_finish = AsyncMock()
	loop = asyncio.get_running_loop()
	t.run(loop, b, db, {}, AsyncMock(), on_finish)
	execution = t.execution
	await asyncio.sleep(0)  # let task enter its first await
	execution.cancel()
	await asyncio.gather(execution, return_exceptions=True)
	_, _, success = on_finish.call_args.args
	assert success is False

@pytest.mark.asyncio
async def testRunOnCancelledLogsOutput():
	t = make_task(processor=_slow_processor)
	db, cursor = make_db()
	b = make_broadcaster()
	on_output = AsyncMock()
	loop = asyncio.get_running_loop()
	t.run(loop, b, db, {}, on_output, None)
	execution = t.execution
	await asyncio.sleep(0)
	execution.cancel()
	await asyncio.gather(execution, return_exceptions=True)
	on_output.assert_called()

#-------------------------------------------------------------------------------
# run — pre/post processing

@pytest.mark.asyncio
async def testRunCallsPreProcessing():
	t = make_task()
	db, cursor = make_db()
	b = make_broadcaster()
	pre = AsyncMock()
	t.pre_processing = pre
	await _run_and_await(t, db, b)
	pre.assert_called_once()

@pytest.mark.asyncio
async def testRunCallsPostProcessing():
	t = make_task()
	db, cursor = make_db()
	b = make_broadcaster()
	post = AsyncMock()
	t.post_processing = post
	await _run_and_await(t, db, b)
	post.assert_called_once()

#-------------------------------------------------------------------------------
# register_self

@pytest.mark.asyncio
async def testRegisterSelfUpdatesIdent():
	t = make_task()
	db, cursor = make_db()
	cursor.fetchone = AsyncMock(return_value=(99, True))
	await t.register_self(db)
	assert t.ident == 99

@pytest.mark.asyncio
async def testRegisterSelfEnablesTask():
	t = make_task()
	db, cursor = make_db()
	cursor.fetchone = AsyncMock(return_value=(1, True))
	await t.disable()
	await t.register_self(db)
	assert t.enabled is True

@pytest.mark.asyncio
async def testRegisterSelfDisablesTask():
	t = make_task()
	db, cursor = make_db()
	cursor.fetchone = AsyncMock(return_value=(1, False))
	await t.register_self(db)
	assert t.enabled is False

@pytest.mark.asyncio
async def testRegisterSelfCommits():
	t = make_task()
	db, cursor = make_db()
	await t.register_self(db)
	db.commit.assert_called_once()

#-------------------------------------------------------------------------------
# TaskManager concrete methods

class ConcreteManager(TaskManager):
	async def execute_tasks(self): pass
	async def stop(self): pass

@pytest.fixture
def manager():
	return ConcreteManager(MagicMock(), MagicMock())

def testTaskManagerAbstractCannotInstantiate():
	with pytest.raises(TypeError):
		TaskManager(MagicMock(), MagicMock())

def testListTasksEmpty(manager):
	assert manager.list_tasks([]) == []

def testListTasksReturnsCorrectShape(manager):
	t = make_task(name="my_task")
	t.package = "pkg"
	manager.loaded_tasks = [t]
	result = manager.list_tasks([])
	assert result[0]['name'] == "my_task"
	assert result[0]['package'] == "pkg"
	assert result[0]['enabled'] is True
	assert 'id' in result[0]

def testGetTaskFoundById(manager):
	t = make_task()
	manager.loaded_tasks = [t]
	assert manager.get_task(t.ident) is t

def testGetTaskNotFound(manager):
	manager.loaded_tasks = []
	assert manager.get_task(999) is None

def testTaskFromSourceFound(manager):
	t = make_task(source="svc.py")
	manager.loaded_tasks = [t]
	assert manager.task_from_source("svc.py") is t

def testTaskFromSourceNotFound(manager):
	manager.loaded_tasks = []
	assert manager.task_from_source("missing.py") is None

def testGetBaseContextReturnsEmptySet(manager):
	assert manager.get_base_context() == set()

#-------------------------------------------------------------------------------
# set_tasks

@pytest.mark.asyncio
async def testSetTasksRegistersEachTask():
	loop = asyncio.get_running_loop()
	manager = ConcreteManager(loop, MagicMock())
	manager.internal_db = AsyncMock()
	t = make_task()
	db, cursor = make_db()
	cursor.fetchone = AsyncMock(return_value=(t.ident, True))
	await manager.set_tasks([t], db)
	await asyncio.sleep(0)
	assert manager.loaded_tasks == [t]

@pytest.mark.asyncio
async def testSetTasksCallsExecuteTasks():
	loop = asyncio.get_running_loop()
	execute_called = []

	class TrackingManager(TaskManager):
		async def execute_tasks(self): execute_called.append(True)
		async def stop(self): pass

	manager = TrackingManager(loop, MagicMock())
	manager.internal_db = AsyncMock()
	t = make_task()
	db, cursor = make_db()
	cursor.fetchone = AsyncMock(return_value=(t.ident, True))
	await manager.set_tasks([t], db)
	await asyncio.sleep(0)
	assert execute_called == [True]

@pytest.mark.asyncio
async def testSetTasksCallsStopFirst():
	loop = asyncio.get_running_loop()
	stop_called = []

	class TrackingManager(TaskManager):
		async def execute_tasks(self): pass
		async def stop(self): stop_called.append(True)

	manager = TrackingManager(loop, MagicMock())
	manager.internal_db = AsyncMock()
	db, _ = make_db()
	await manager.set_tasks([], db)
	assert stop_called == [True]

#-------------------------------------------------------------------------------

if __name__ == "__main__":
	pytest.main([__file__, "-v"])
