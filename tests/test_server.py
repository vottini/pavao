
import sys
sys.path.append('..')

import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch, call

from pavao.server import Server, create_processing_pipeline
from pavao.supplier import ParameterException
from pavao.registry import Registry

#-------------------------------------------------------------------------------
# helpers

def make_server(**overrides):
	server = MagicMock()
	server.endpoints = {}
	server.tasks = {}
	server.services = {}
	server.modules_dir = '/fake'
	server.loaded_settings = MagicMock()
	server._reload_lock = asyncio.Lock()
	server._parsed_tasks = {}
	server._parsed_services = {}
	server._filter_list = []
	server.parametering.prepare_context = AsyncMock(return_value={})
	server.parametering.destroy = AsyncMock()
	server.parametering.unknown_deps.return_value = None
	server.parametering.create_wrappers.return_value = (None, None)
	server.parametering.change_base.return_value = MagicMock(
		**{'create_wrappers.return_value': (None, None)}
	)
	server.filtering.list_filters.return_value = []
	server.register_endpoints = AsyncMock()
	server.restart_tasks = AsyncMock()
	server.load_modules = AsyncMock()
	server.http_handler.update_registry = AsyncMock()
	for k, v in overrides.items():
		setattr(server, k, v)
	return server


def capture_update_coro(server, creations=set(), deletions=set(), updates=set()):
	captured = []
	def capture(coro, loop):
		captured.append(coro)
		return MagicMock()

	with patch('pavao.server.jsonbp'), \
		 patch('pavao.server.asyncio.run_coroutine_threadsafe', side_effect=capture), \
		 patch('pavao.server.load_component', return_value=None):
		Server.update_modules(server, creations, deletions, updates)

	assert len(captured) == 1
	return captured[0]

#-------------------------------------------------------------------------------
# create_processing_pipeline

@pytest.mark.asyncio
async def testPipelineRunsPreFiltersProcessorAndPostFiltersInOrder():
	order = []
	async def pre(ctx): order.append('pre')
	async def allower(ctx): order.append('allow'); return True
	async def processor(ctx): order.append('proc')
	async def post(ctx): order.append('post')

	pipeline = create_processing_pipeline([pre], [allower], processor, [post])
	await pipeline({})
	assert order == ['pre', 'allow', 'proc', 'post']


@pytest.mark.asyncio
async def testPipelineRunsProcessorWithNoFilters():
	called = []
	async def processor(ctx): called.append(True)

	pipeline = create_processing_pipeline([], [], processor, [])
	await pipeline({})
	assert called == [True]


@pytest.mark.asyncio
async def testPipelineSkipsProcessorWhenAllowerDenies():
	order = []
	async def allower(ctx): order.append('allow'); return False
	async def processor(ctx): order.append('proc')
	async def post(ctx): order.append('post')

	pipeline = create_processing_pipeline([], [allower], processor, [post])
	await pipeline({})
	assert 'proc' not in order
	assert 'post' in order


@pytest.mark.asyncio
async def testPipelineStopsAtFirstDenyingAllower():
	order = []
	async def deny(ctx): order.append('deny'); return False
	async def allow(ctx): order.append('allow'); return True
	async def processor(ctx): order.append('proc')

	pipeline = create_processing_pipeline([], [deny, allow], processor, [])
	await pipeline({})
	assert order == ['deny']


@pytest.mark.asyncio
async def testPipelinePostFiltersRunEvenWhenProcessorRaises():
	order = []
	async def processor(ctx): raise RuntimeError("boom")
	async def post(ctx): order.append('post')

	pipeline = create_processing_pipeline([], [], processor, [post])
	with pytest.raises(RuntimeError):
		await pipeline({})
	assert 'post' in order

#-------------------------------------------------------------------------------
# Server.__init__ / _startup / _shutdown

def _make_real_server():
	with patch('pavao.server.PathMonitor'), \
		 patch('pavao.server.Broadcaster'), \
		 patch('pavao.server.ParameterFactory'), \
		 patch('pavao.server.FilterCollection'), \
		 patch('pavao.server.lifespan') as mock_lifespan, \
		 patch('pavao.server.http'):
		server = Server.__new__(Server)
		Server.__init__(server, 'config.yml', False, None, '/fake_modules')

	init_fn, stop_fn = mock_lifespan.LifespanHandler.call_args.args
	return server, init_fn, stop_fn


@pytest.mark.asyncio
async def testServerStartupStartsAllComponents():
	server, init_fn, _ = _make_real_server()

	server.http_handler.init = AsyncMock()
	server.parametering.init = AsyncMock()
	server.filtering.init = AsyncMock()
	server._build_filter_list = AsyncMock()
	server.load_user_modules = AsyncMock()
	server.register_endpoints = AsyncMock()
	server.restart_tasks = AsyncMock()

	with patch('pavao.server.load_settings', return_value=MagicMock()), \
		 patch('pavao.server.start_logging'), \
		 patch('pavao.server.load_folder'), \
		 patch('pavao.server.Scheduler'), \
		 patch('pavao.server.Daemon'):
		result = await init_fn()

	assert result is True
	server._build_filter_list.assert_called_once()
	server.load_user_modules.assert_called_once()
	server.register_endpoints.assert_called_once()
	server.restart_tasks.assert_called_once()


@pytest.mark.asyncio
async def testServerStartupInitializesReloadLock():
	server, init_fn, _ = _make_real_server()

	server.http_handler.init = AsyncMock()
	server.parametering.init = AsyncMock()
	server.filtering.init = AsyncMock()
	server._build_filter_list = AsyncMock()
	server.load_user_modules = AsyncMock()
	server.register_endpoints = AsyncMock()
	server.restart_tasks = AsyncMock()
	server._reload_lock = None

	with patch('pavao.server.load_settings', return_value=MagicMock()), \
		 patch('pavao.server.start_logging'), \
		 patch('pavao.server.load_folder'), \
		 patch('pavao.server.Scheduler'), \
		 patch('pavao.server.Daemon'):
		await init_fn()

	assert isinstance(server._reload_lock, asyncio.Lock)


@pytest.mark.asyncio
async def testServerShutdownStopsAllComponents():
	server, _, stop_fn = _make_real_server()

	server.scheduler = MagicMock()
	server.scheduler.stop = AsyncMock()
	server.daemon = MagicMock()
	server.daemon.stop = AsyncMock()
	server.parametering.shutdown = AsyncMock()

	with patch('pavao.server.stop_logging'):
		await stop_fn()

	server.scheduler.stop.assert_called_once()
	server.daemon.stop.assert_called_once()
	server.parametering.shutdown.assert_called_once()

#-------------------------------------------------------------------------------
# load_modules

@pytest.mark.asyncio
async def testLoadModulesReturnsEarlyWithNoScripts():
	server = make_server()
	await Server.load_modules(server, {}, {}, {})
	server.parametering.prepare_context.assert_not_called()


@pytest.mark.asyncio
async def testLoadModulesWarnsAndSkipsNonDictSpec():
	server = make_server()
	endpoints = {}
	def bad(): return ["not", "a", "dict"]

	with patch('pavao.server.Logger') as mock_logger:
		await Server.load_modules(server, endpoints, {}, {}, ('/fake/ep.py', ('ENDPOINT', bad)))

	assert '/fake/ep.py' not in endpoints
	mock_logger.warning.assert_called()
	assert 'dict' in mock_logger.warning.call_args.args[0]


@pytest.mark.asyncio
async def testLoadModulesSilentlySkipsNoneSpec():
	server = make_server()
	endpoints = {}
	def none_init(): return None

	with patch('pavao.server.Logger') as mock_logger:
		await Server.load_modules(server, endpoints, {}, {}, ('/fake/ep.py', ('ENDPOINT', none_init)))

	assert '/fake/ep.py' not in endpoints
	mock_logger.warning.assert_not_called()


@pytest.mark.asyncio
async def testLoadModulesStoresDictSpec():
	server = make_server()
	endpoints = {}
	def good(): return {'method': 'GET', 'path': '/x', 'processor': lambda: None}

	await Server.load_modules(server, endpoints, {}, {}, ('/fake/ep.py', ('ENDPOINT', good)))
	assert '/fake/ep.py' in endpoints


@pytest.mark.asyncio
async def testLoadModulesWarnsOnKeyError():
	server = make_server()
	server.parametering.prepare_context = AsyncMock(side_effect=KeyError('missing'))
	endpoints = {}

	with patch('pavao.server.Logger') as mock_logger:
		await Server.load_modules(server, endpoints, {}, {}, ('/fake/ep.py', ('ENDPOINT', lambda: {})))

	assert '/fake/ep.py' not in endpoints
	mock_logger.warning.assert_called()
	assert 'missing' in mock_logger.warning.call_args.args[0]


@pytest.mark.asyncio
async def testLoadModulesWarnsOnParameterException():
	server = make_server()
	server.parametering.prepare_context = AsyncMock(side_effect=ParameterException("bad param"))
	endpoints = {}

	with patch('pavao.server.Logger') as mock_logger:
		await Server.load_modules(server, endpoints, {}, {}, ('/fake/ep.py', ('ENDPOINT', lambda: {})))

	assert '/fake/ep.py' not in endpoints
	mock_logger.warning.assert_called()


@pytest.mark.asyncio
async def testLoadModulesWarnsOnGenericException():
	server = make_server()
	server.parametering.prepare_context = AsyncMock(side_effect=ValueError("unexpected"))
	endpoints = {}

	with patch('pavao.server.Logger') as mock_logger, \
		 patch('pavao.server.traceback'):
		await Server.load_modules(server, endpoints, {}, {}, ('/fake/ep.py', ('ENDPOINT', lambda: {})))

	assert '/fake/ep.py' not in endpoints
	mock_logger.warning.assert_called()


@pytest.mark.asyncio
async def testLoadModulesDoesNotPassLoadedSettingsToDestroy():
	server = make_server()
	destroyed_params = []
	async def capture_destroy(param, value):
		destroyed_params.append(param)
	server.parametering.destroy = capture_destroy

	def good(): return {'method': 'GET', 'path': '/x', 'processor': lambda: None}
	await Server.load_modules(server, {}, {}, {}, ('/fake/ep.py', ('ENDPOINT', good)))

	assert 'loaded_settings' not in destroyed_params


@pytest.mark.asyncio
async def testLoadModulesDestroysInjectedParameters():
	server = make_server()
	server.parametering.prepare_context = AsyncMock(
		return_value={'loaded_settings': MagicMock(), 'db': 'conn'})

	def good(): return {'method': 'GET', 'path': '/x', 'processor': lambda: None}
	await Server.load_modules(server, {}, {}, {}, ('/fake/ep.py', ('ENDPOINT', good)))

	server.parametering.destroy.assert_called_once_with('db', 'conn')

#-------------------------------------------------------------------------------
# load_builtin_foundation / load_user_foundation / load_user_modules

def testLoadBuiltinFoundationCallsLoadFolder():
	server = make_server()
	with patch('pavao.server.load_folder') as mock_lf:
		Server.load_builtin_foundation(server)
	assert mock_lf.call_count == 1
	path_arg = mock_lf.call_args.args[0]
	assert 'builtin' in path_arg and 'foundation' in path_arg


def testLoadUserFoundationSkipsWhenNone():
	server = make_server()
	with patch('pavao.server.load_folder') as mock_lf:
		Server.load_user_foundation(server, None)
	mock_lf.assert_not_called()


def testLoadUserFoundationCallsLoadFolderWhenSet():
	server = make_server()
	with patch('pavao.server.load_folder') as mock_lf:
		Server.load_user_foundation(server, '/my/foundation')
	mock_lf.assert_called_once_with('/my/foundation', True)


@pytest.mark.asyncio
async def testLoadUserModulesCallsLoadComponentsDirAndLoadModules():
	server = make_server()
	fake_scripts = [('/fake/ep.py', ('ENDPOINT', lambda: {}))]

	with patch('pavao.server.load_components_dir', return_value=fake_scripts) as mock_lcd:
		await Server.load_user_modules(server)

	mock_lcd.assert_called_once_with(server.modules_dir, True)
	server.load_modules.assert_called_once()

#-------------------------------------------------------------------------------
# _build_filter_list

@pytest.mark.asyncio
async def testBuildFilterListEmptyWhenNoFilters():
	server = make_server()
	server.filtering.list_filters.return_value = []

	await Server._build_filter_list(server)

	assert server._filter_list == []


@pytest.mark.asyncio
async def testBuildFilterListBuildsWrappedFilters():
	server = make_server()
	def enabler(endpoint_specs): return True
	def allower(): return True
	server.filtering.list_filters.return_value = [('MyFilter', enabler, allower)]

	await Server._build_filter_list(server)

	assert len(server._filter_list) == 1
	_, stored_allower = server._filter_list[0]
	assert stored_allower is allower


@pytest.mark.asyncio
async def testBuildFilterListRaisesOnParameterException():
	server = make_server()
	server.filtering.list_filters.return_value = [('MyFilter', lambda: True, lambda: True)]
	server.parametering.change_base.return_value.create_wrappers.side_effect = ParameterException("bad")

	with pytest.raises(ParameterException):
		await Server._build_filter_list(server)

#-------------------------------------------------------------------------------
# register_endpoints

@pytest.mark.asyncio
async def testRegisterEndpointsWithNoEndpointsUpdatesRegistry():
	server = make_server()

	with patch('pavao.server.Registry') as mock_reg:
		await Server.register_endpoints(server)

	server.http_handler.update_registry.assert_called_once_with(mock_reg.return_value)
	mock_reg.return_value.add_endpoint.assert_not_called()


@pytest.mark.asyncio
async def testRegisterEndpointsAddsValidEndpointToRegistry():
	server = make_server()
	def processor(): pass
	server.endpoints = {'/fake/ep.py': {'method': 'GET', 'path': '/hello', 'processor': processor}}

	with patch('pavao.server.Registry') as mock_reg:
		await Server.register_endpoints(server)

	mock_reg.return_value.add_endpoint.assert_called_once()
	args = mock_reg.return_value.add_endpoint.call_args.args
	assert args[0] == 'GET'
	assert args[1] == '/hello'


@pytest.mark.asyncio
async def testRegisterEndpointsSkipsEndpointWithUnknownDep():
	server = make_server()
	server.parametering.unknown_deps.return_value = 'missing_param'
	def processor(): pass
	server.endpoints = {'/fake/ep.py': {'method': 'GET', 'path': '/hello', 'processor': processor}}

	with patch('pavao.server.Registry') as mock_reg, \
		 patch('pavao.server.Logger') as mock_logger:
		await Server.register_endpoints(server)

	mock_reg.return_value.add_endpoint.assert_not_called()
	mock_logger.warning.assert_called()


@pytest.mark.asyncio
async def testRegisterEndpointsSkipsEndpointOnWrapperParameterException():
	server = make_server()
	server.parametering.create_wrappers.side_effect = ParameterException("bad dep")
	def processor(): pass
	server.endpoints = {'/fake/ep.py': {'method': 'GET', 'path': '/hello', 'processor': processor}}

	with patch('pavao.server.Registry') as mock_reg, \
		 patch('pavao.server.Logger') as mock_logger:
		await Server.register_endpoints(server)

	mock_reg.return_value.add_endpoint.assert_not_called()
	mock_logger.warning.assert_called()


@pytest.mark.asyncio
async def testRegisterEndpointsSkipsEndpointWithMissingFields():
	server = make_server()
	server.endpoints = {'/fake/ep.py': {}}  # missing method/path/processor

	with patch('pavao.server.Registry') as mock_reg, \
		 patch('pavao.server.Logger') as mock_logger:
		await Server.register_endpoints(server)

	mock_reg.return_value.add_endpoint.assert_not_called()
	mock_logger.warning.assert_called()


@pytest.mark.asyncio
async def testRegisterEndpointsAttachesEnabledFilter():
	server = make_server()
	def allower(): return True

	async def wrapped_enabler(context): return True
	server._filter_list = [(wrapped_enabler, allower)]
	def processor(): pass
	server.endpoints = {'/fake/ep.py': {'method': 'GET', 'path': '/hello', 'processor': processor}}

	with patch('pavao.server.Registry'):
		await Server.register_endpoints(server)

	calls = server.parametering.create_wrappers.call_args_list
	called_fns = [c.args[0] for c in calls]
	assert allower in called_fns


@pytest.mark.asyncio
async def testRegisterEndpointsSkipsDisabledFilter():
	server = make_server()
	def allower(): return True

	async def wrapped_enabler(context): return False
	server._filter_list = [(wrapped_enabler, allower)]
	def processor(): pass
	server.endpoints = {'/fake/ep.py': {'method': 'GET', 'path': '/hello', 'processor': processor}}

	with patch('pavao.server.Registry'):
		await Server.register_endpoints(server)

	calls = server.parametering.create_wrappers.call_args_list
	called_fns = [c.args[0] for c in calls]
	assert allower not in called_fns

#-------------------------------------------------------------------------------
# update_modules — dependency tracking and service unload

@pytest.mark.asyncio
async def testUpdateModulesTracksScriptWithDependeesAsUpdatedDependency():
	file_path = '/fake/module.py'
	dependent = '/fake/dependent.py'
	server = make_server()
	server.endpoints = {dependent: {}}

	captured = []
	def capture(coro, loop): captured.append(coro); return MagicMock()

	with patch('pavao.server.jsonbp'), \
		 patch('pavao.server.asyncio.run_coroutine_threadsafe', side_effect=capture), \
		 patch('pavao.server.retrieve_dependees', return_value={dependent}), \
		 patch('pavao.server.load_component', return_value=None), \
		 patch('pavao.server.load_module'):
		Server.update_modules(server, set(), set(), {file_path})
		await captured[0]

	assert dependent not in server.endpoints


@pytest.mark.asyncio
async def testUpdateModulesTracksNonPythonFileDependees():
	non_py = '/fake/template.html'
	dependent = '/fake/dependent.py'
	server = make_server()
	server.endpoints = {dependent: {}}

	captured = []
	def capture(coro, loop): captured.append(coro); return MagicMock()

	with patch('pavao.server.jsonbp'), \
		 patch('pavao.server.asyncio.run_coroutine_threadsafe', side_effect=capture), \
		 patch('pavao.server.retrieve_dependees', return_value={dependent}), \
		 patch('pavao.server.load_component', return_value=None):
		Server.update_modules(server, set(), {non_py}, set())
		await captured[0]

	assert dependent not in server.endpoints


@pytest.mark.asyncio
async def testUpdateModulesUnloadsService():
	file_path = '/fake/service.py'
	server = make_server()
	server.services = {file_path: {}}
	server._parsed_services = {file_path: MagicMock()}

	captured = []
	def capture(coro, loop): captured.append(coro); return MagicMock()

	with patch('pavao.server.jsonbp'), \
		 patch('pavao.server.asyncio.run_coroutine_threadsafe', side_effect=capture), \
		 patch('pavao.server.load_component', return_value=None):
		Server.update_modules(server, set(), {file_path}, set())
		await captured[0]

	assert file_path not in server.services
	assert file_path not in server._parsed_services
	server.daemon.stop_module.assert_called_once_with(file_path)


@pytest.mark.asyncio
async def testUpdateModulesInvalidatesParsedTaskCache():
	file_path = '/fake/task.py'
	server = make_server()
	server.tasks = {file_path: {}}
	server._parsed_tasks = {file_path: MagicMock()}

	coro = capture_update_coro(server, deletions={file_path})
	await coro

	assert file_path not in server._parsed_tasks


@pytest.mark.asyncio
async def testUpdateModulesCallsLoadModuleForDependencies():
	file_path = '/fake/module.py'
	dependent = '/fake/dependent.py'
	server = make_server()

	captured = []
	def capture(coro, loop): captured.append(coro); return MagicMock()

	with patch('pavao.server.jsonbp'), \
		 patch('pavao.server.asyncio.run_coroutine_threadsafe', side_effect=capture), \
		 patch('pavao.server.retrieve_dependees', return_value={dependent}), \
		 patch('pavao.server.load_component', return_value=None), \
		 patch('pavao.server.load_module') as mock_load_module:
		Server.update_modules(server, set(), set(), {file_path})
		await captured[0]

	mock_load_module.assert_called_once_with(file_path)

#-------------------------------------------------------------------------------
# update_modules — previously tested behaviors (kept for completeness)

def testUpdateModulesLogsExceptionFromProcessUpdates():
	server = make_server()

	failed_future = MagicMock()
	failed_future.cancelled.return_value = False
	failed_future.exception.return_value = RuntimeError("db error")

	captured_callback = []
	def capture(coro, loop):
		coro.close()
		future = MagicMock()
		future.add_done_callback.side_effect = lambda cb: captured_callback.append(cb)
		return future

	with patch('pavao.server.jsonbp'), \
		 patch('pavao.server.asyncio.run_coroutine_threadsafe', side_effect=capture), \
		 patch('pavao.server.Logger') as mock_logger, \
		 patch('pavao.server.traceback'):
		Server.update_modules(server, set(), set(), set())
		captured_callback[0](failed_future)

	mock_logger.error.assert_called()
	assert 'db error' in mock_logger.error.call_args_list[0].args[0]


def testUpdateModulesDoesNotLogWhenFutureSucceeds():
	server = make_server()

	ok_future = MagicMock()
	ok_future.cancelled.return_value = False
	ok_future.exception.return_value = None

	captured_callback = []
	def capture(coro, loop):
		coro.close()
		future = MagicMock()
		future.add_done_callback.side_effect = lambda cb: captured_callback.append(cb)
		return future

	with patch('pavao.server.jsonbp'), \
		 patch('pavao.server.asyncio.run_coroutine_threadsafe', side_effect=capture), \
		 patch('pavao.server.Logger') as mock_logger:
		Server.update_modules(server, set(), set(), set())
		captured_callback[0](ok_future)

	mock_logger.error.assert_not_called()


def testUpdateModulesSchedulesExactlyOneCoroutine():
	server = make_server()
	count = []
	def capture_and_close(coro, loop):
		count.append(1)
		coro.close()
		return MagicMock()
	with patch('pavao.server.jsonbp'), \
		 patch('pavao.server.asyncio.run_coroutine_threadsafe', side_effect=capture_and_close):
		Server.update_modules(server, set(), set(), set())
	assert sum(count) == 1


@pytest.mark.asyncio
async def testUpdateModulesLoadsBeforeRegisteringAndRestarting():
	order = []
	async def mock_load(*a, **kw): order.append('load')
	async def mock_register(): order.append('register')
	async def mock_restart(): order.append('restart')

	server = make_server()
	server.load_modules = mock_load
	server.register_endpoints = mock_register
	server.restart_tasks = mock_restart

	captured = []
	def capture(coro, loop): captured.append(coro); return MagicMock()

	fake_spec = ('ENDPOINT', lambda: {'method': 'GET', 'path': '/x', 'processor': lambda: None})
	with patch('pavao.server.jsonbp'), \
		 patch('pavao.server.asyncio.run_coroutine_threadsafe', side_effect=capture), \
		 patch('pavao.server.load_component', return_value=fake_spec):
		Server.update_modules(server, {'/fake/ep.py'}, set(), set())
		await captured[0]

	assert order == ['load', 'register', 'restart']


@pytest.mark.asyncio
async def testUpdateModulesUnloadsFromFirstMatchingDictOnly():
	file_path = '/fake/module.py'
	server = make_server()
	server.endpoints = {file_path: {}}
	server.tasks = {file_path: {}}

	coro = capture_update_coro(server, deletions={file_path})
	await coro

	assert file_path not in server.endpoints
	assert file_path in server.tasks


@pytest.mark.asyncio
async def testUpdateModulesUnloadsBeforeLoading():
	file_path = '/fake/module.py'
	server = make_server()
	server.endpoints = {file_path: {'method': 'GET', 'path': '/old', 'processor': None}}

	sequence = []
	async def mock_load(ep_dest, *a, **kw): sequence.append(('load', file_path in ep_dest))
	server.load_modules = mock_load

	fake_spec = ('ENDPOINT', lambda: {'method': 'GET', 'path': '/new', 'processor': None})
	captured = []
	def capture(coro, loop): captured.append(coro); return MagicMock()

	with patch('pavao.server.jsonbp'), \
		 patch('pavao.server.asyncio.run_coroutine_threadsafe', side_effect=capture), \
		 patch('pavao.server.load_component', return_value=fake_spec):
		Server.update_modules(server, set(), set(), {file_path})
		await captured[0]

	assert sequence == [('load', False)]


@pytest.mark.asyncio
async def testUpdateModulesReloadLockPreventsParallelExecution():
	server = make_server()

	captured = []
	def capture(coro, loop): captured.append(coro); return MagicMock()

	with patch('pavao.server.jsonbp'), \
		 patch('pavao.server.asyncio.run_coroutine_threadsafe', side_effect=capture), \
		 patch('pavao.server.load_component', return_value=None):
		Server.update_modules(server, set(), set(), set())

	await server._reload_lock.acquire()

	run_task = asyncio.create_task(captured[0])
	await asyncio.sleep(0)
	assert not run_task.done()

	server._reload_lock.release()
	await run_task

#-------------------------------------------------------------------------------
# restart_tasks

@pytest.mark.asyncio
async def testRestartTasksDestroysInternalDb():
	server = make_server()
	mock_db = MagicMock()
	server.parametering.produce = AsyncMock(return_value=mock_db)
	server.scheduler.set_tasks = AsyncMock()
	server.daemon.set_tasks = AsyncMock()
	server.parse_tasks = MagicMock(return_value=[])

	await Server.restart_tasks(server)
	server.parametering.destroy.assert_called_once_with('task_store', mock_db)


@pytest.mark.asyncio
async def testRestartTasksDestroysInternalDbEvenOnException():
	server = make_server()
	mock_db = MagicMock()
	server.parametering.produce = AsyncMock(return_value=mock_db)
	server.scheduler.set_tasks = AsyncMock(side_effect=RuntimeError("boom"))
	server.parse_tasks = MagicMock(return_value=[])

	with pytest.raises(RuntimeError):
		await Server.restart_tasks(server)

	server.parametering.destroy.assert_called_once_with('task_store', mock_db)


@pytest.mark.asyncio
async def testRestartTasksPassesCachesToParseTasks():
	server = make_server()
	server._parsed_tasks = {'t': MagicMock()}
	server._parsed_services = {'s': MagicMock()}
	server.parametering.produce = AsyncMock(return_value=MagicMock())
	server.scheduler.set_tasks = AsyncMock()
	server.daemon.set_tasks = AsyncMock()

	cache_args = []
	def capture_parse(modules, manager, cache):
		cache_args.append(cache)
		return []
	server.parse_tasks = capture_parse

	await Server.restart_tasks(server)

	assert server._parsed_tasks in cache_args
	assert server._parsed_services in cache_args

#-------------------------------------------------------------------------------
# parse_tasks

def testParseTasksHappyPath():
	server = make_server()
	async def processor(): yield "output"

	mock_task = MagicMock()
	mock_task.processor = processor

	mock_manager = MagicMock()
	mock_manager.get_base_context.return_value = set()
	mock_manager.ctor.return_value = mock_task

	mock_tp = MagicMock()
	mock_tp.unknown_deps.return_value = None
	mock_tp.create_wrappers.return_value = (None, None)
	server.parametering.change_base.return_value = mock_tp

	result = Server.parse_tasks(server, {'/fake/task.py': {}}, mock_manager, {})

	assert len(result) == 1
	assert result[0] is mock_task
	assert mock_task.pre_processing is None
	assert mock_task.post_processing is None


def testParseTasksCachesAndReusesParsedTask():
	server = make_server()
	mock_task = MagicMock()
	cache = {'/fake/task.py': mock_task}

	mock_manager = MagicMock()
	mock_manager.get_base_context.return_value = set()
	server.parametering.change_base.return_value = MagicMock()

	result = Server.parse_tasks(server, {'/fake/task.py': {}}, mock_manager, cache)

	assert result == [mock_task]
	mock_manager.ctor.assert_not_called()


def testParseTasksAddsToCacheAfterParsing():
	server = make_server()
	async def processor(): yield "output"

	mock_task = MagicMock()
	mock_task.processor = processor

	mock_manager = MagicMock()
	mock_manager.get_base_context.return_value = set()
	mock_manager.ctor.return_value = mock_task

	mock_tp = MagicMock()
	mock_tp.unknown_deps.return_value = None
	mock_tp.create_wrappers.return_value = (None, None)
	server.parametering.change_base.return_value = mock_tp

	cache = {}
	Server.parse_tasks(server, {'/fake/task.py': {}}, mock_manager, cache)

	assert '/fake/task.py' in cache
	assert cache['/fake/task.py'] is mock_task


def testParseTasksSkipsTaskWithUnknownDep():
	server = make_server()
	async def processor(): yield "output"

	mock_task = MagicMock()
	mock_task.processor = processor

	mock_manager = MagicMock()
	mock_manager.get_base_context.return_value = set()
	mock_manager.ctor.return_value = mock_task

	mock_tp = MagicMock()
	mock_tp.unknown_deps.return_value = 'missing_param'
	server.parametering.change_base.return_value = mock_tp

	with patch('pavao.server.Logger') as mock_logger:
		result = Server.parse_tasks(server, {'/fake/task.py': {}}, mock_manager, {})

	assert result == []
	mock_logger.warning.assert_called()


def testParseTasksSkipsTaskWithKeyError():
	server = make_server()
	mock_manager = MagicMock()
	mock_manager.get_base_context.return_value = set()
	mock_manager.ctor.side_effect = KeyError('processor')
	server.parametering.change_base.return_value = MagicMock()

	with patch('pavao.server.Logger') as mock_logger:
		result = Server.parse_tasks(server, {'/fake/task.py': {}}, mock_manager, {})

	assert result == []
	mock_logger.warning.assert_called()


def testParseTasksSkipsTaskOnGenericException():
	server = make_server()
	mock_manager = MagicMock()
	mock_manager.get_base_context.return_value = set()
	mock_manager.ctor.side_effect = RuntimeError("unexpected")
	server.parametering.change_base.return_value = MagicMock()

	with patch('pavao.server.Logger') as mock_logger:
		result = Server.parse_tasks(server, {'/fake/task.py': {}}, mock_manager, {})

	assert result == []
	mock_logger.warning.assert_called()

#-------------------------------------------------------------------------------
# deactivate

@pytest.mark.asyncio
async def testDeactivateCallsHttpHandlerDeactivateAndSchedulesShutdown():
	server = make_server()
	server.broadcaster.announce_shutdown = AsyncMock()

	captured_coro = []
	server.loop.create_task.side_effect = lambda coro: captured_coro.append(coro)

	Server.deactivate(server)

	server.http_handler.deactivate.assert_called_once()
	assert len(captured_coro) == 1
	await captured_coro[0]
	server.broadcaster.announce_shutdown.assert_called_once()

#-------------------------------------------------------------------------------
# get_app

@pytest.mark.asyncio
async def testGetAppDispatchesHttpScope():
	server = make_server()
	server.http_handler.handle = AsyncMock()
	server.lifespan_handler.handle = AsyncMock()

	app = Server.get_app(server)
	scope = {'type': 'http'}
	await app(scope, MagicMock(), MagicMock())

	server.http_handler.handle.assert_called_once()
	server.lifespan_handler.handle.assert_not_called()


@pytest.mark.asyncio
async def testGetAppDispatchesLifespanScope():
	server = make_server()
	server.http_handler.handle = AsyncMock()
	server.lifespan_handler.handle = AsyncMock()

	app = Server.get_app(server)
	scope = {'type': 'lifespan'}
	await app(scope, MagicMock(), MagicMock())

	server.lifespan_handler.handle.assert_called_once()
	server.http_handler.handle.assert_not_called()


@pytest.mark.asyncio
async def testGetAppIgnoresUnknownScope():
	server = make_server()
	server.http_handler.handle = AsyncMock()
	server.lifespan_handler.handle = AsyncMock()

	app = Server.get_app(server)
	await app({'type': 'websocket'}, MagicMock(), MagicMock())

	server.http_handler.handle.assert_not_called()
	server.lifespan_handler.handle.assert_not_called()

#-------------------------------------------------------------------------------

if __name__ == "__main__":
	pytest.main([__file__, "-v"])
