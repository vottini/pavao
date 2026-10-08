
import sys
sys.path.append('..')

import pytest
from unittest.mock import AsyncMock, MagicMock
from pavao.supplier import ParameterSupplier, ParameterFactory, ParameterException

#-------------------------------------------------------------------------------
# helpers

async def _ctor_x(): return "x_val"
async def _ctor_y(x): return f"y({x})"
async def _ctor_z(y): return f"z({y})"

def make_factory(base=None):
	return ParameterFactory(base or set())

def make_populated_factory(params, deps, base=None):
	f = make_factory(base)
	f.parameters = params
	f.dependencies = deps
	return f

@pytest.fixture(autouse=True)
def reset_supplier_registry():
	original = ParameterSupplier.implementations[:]
	yield
	ParameterSupplier.implementations[:] = original

#-------------------------------------------------------------------------------
# ParameterSupplier

def testParameterSupplierSubclassIsRegistered():
	before = len(ParameterSupplier.implementations)
	class MySup(ParameterSupplier): pass
	assert len(ParameterSupplier.implementations) == before + 1

def testParameterSupplierDefaultSuppliesNothing():
	class MySup(ParameterSupplier): pass
	assert MySup().parameters_supplied() == {}

#-------------------------------------------------------------------------------
# init — supplier discovery

@pytest.mark.asyncio
async def testInitSkipsSupplierWithNoParameters():
	class EmptySup(ParameterSupplier):
		def parameters_supplied(self): return {}
	factory = make_factory()
	await factory.init({})
	assert factory.suppliers == []

@pytest.mark.asyncio
async def testInitRegistersSuppliedParameters():
	class XSup(ParameterSupplier):
		def parameters_supplied(self): return {'x': (_ctor_x, None)}
	factory = make_factory()
	await factory.init({})
	assert 'x' in factory.parameters

@pytest.mark.asyncio
async def testInitRaisesOnAmbiguousParameter():
	class A(ParameterSupplier):
		def parameters_supplied(self): return {'x': (_ctor_x, None)}
	class B(ParameterSupplier):
		def parameters_supplied(self): return {'x': (_ctor_x, None)}
	with pytest.raises(ParameterException):
		await make_factory().init({})

@pytest.mark.asyncio
async def testInitRaisesWhenBaseParameterClashes():
	class A(ParameterSupplier):
		def parameters_supplied(self): return {'request': (_ctor_x, None)}
	with pytest.raises(ParameterException):
		await make_factory(base={'request'}).init({})

#-------------------------------------------------------------------------------
# init — parameter graph validation

@pytest.mark.asyncio
async def testInitRaisesOnUnknownDependency():
	async def bad_ctor(ghost): return "x"
	class BadSup(ParameterSupplier):
		def parameters_supplied(self): return {'x': (bad_ctor, None)}
	with pytest.raises(ParameterException):
		await make_factory().init({})

@pytest.mark.asyncio
async def testInitAllowsBaseParameterAsDependency():
	async def ctor(request): return "x"
	class MySup(ParameterSupplier):
		def parameters_supplied(self): return {'x': (ctor, None)}
	factory = make_factory(base={'request'})
	await factory.init({})
	assert 'x' in factory.parameters

@pytest.mark.asyncio
async def testInitRaisesOnCircularParameterDependency():
	async def ctor_a(b): return "a"
	async def ctor_b(a): return "b"
	class CircSup(ParameterSupplier):
		def parameters_supplied(self):
			return {'a': (ctor_a, None), 'b': (ctor_b, None)}
	with pytest.raises(ParameterException):
		await make_factory().init({})

#-------------------------------------------------------------------------------
# init — supplier initialization order

@pytest.mark.asyncio
async def testInitCallsInitializeOnEachSupplier():
	initialized = []
	class MySup(ParameterSupplier):
		def parameters_supplied(self): return {'x': (_ctor_x, None)}
		async def initialize(self): initialized.append(True)
	await make_factory().init({})
	assert initialized == [True]

@pytest.mark.asyncio
async def testInitInitializesInDependencyOrder():
	order = []
	class First(ParameterSupplier):
		def parameters_supplied(self): return {'x': (_ctor_x, None)}
		async def initialize(self): order.append('first')
	class Second(ParameterSupplier):
		def parameters_supplied(self): return {'y': (_ctor_y, None)}
		async def initialize(self, x): order.append('second')
	await make_factory().init({})
	assert order == ['first', 'second']

@pytest.mark.asyncio
async def testInitRaisesOnCircularSupplierInitDependency():
	async def ctor_a(): return "a"
	async def ctor_b(): return "b"
	class SupA(ParameterSupplier):
		def parameters_supplied(self): return {'a': (ctor_a, None)}
		async def initialize(self, b): pass
	class SupB(ParameterSupplier):
		def parameters_supplied(self): return {'b': (ctor_b, None)}
		async def initialize(self, a): pass
	with pytest.raises(ParameterException):
		await make_factory().init({})

@pytest.mark.asyncio
async def testInitRaisesOnUnknownInitializeDependency():
	class BadSup(ParameterSupplier):
		def parameters_supplied(self): return {'x': (_ctor_x, None)}
		async def initialize(self, ghost): pass
	with pytest.raises(ParameterException):
		await make_factory().init({})

#-------------------------------------------------------------------------------
# create_wrappers

def testCreateWrappersReturnsNoneNoneWhenNoGeneratedDeps():
	async def fnc(request): pass
	f = make_populated_factory({}, {}, base={'request'})
	creation, teardown = f.create_wrappers(fnc)
	assert creation is None and teardown is None

def testCreateWrappersRaisesForUnknownParameter():
	async def fnc(ghost): pass
	with pytest.raises(ParameterException):
		make_populated_factory({}, {}).create_wrappers(fnc)

@pytest.mark.asyncio
async def testCreateWrappersCreationProducesParameter():
	f = make_populated_factory(
		params={'x': (_ctor_x, None)},
		deps={'x': ()}
	)
	async def fnc(x): pass
	creation, _ = f.create_wrappers(fnc)
	context = {}
	await creation(context)
	assert context['x'] == 'x_val'

@pytest.mark.asyncio
async def testCreateWrappersCreationRespectsOrder():
	produced = []
	async def make_x(): produced.append('x'); return 'x_val'
	async def make_y(x): produced.append('y'); return 'y_val'
	f = make_populated_factory(
		params={'x': (make_x, None), 'y': (make_y, None)},
		deps={'x': (), 'y': ('x',)}
	)
	async def fnc(y): pass
	creation, _ = f.create_wrappers(fnc)
	await creation({})
	assert produced == ['x', 'y']

@pytest.mark.asyncio
async def testCreateWrappersTearDownInReverseOrder():
	destroyed = []
	async def dtor_x(v): destroyed.append('x')
	async def dtor_y(v): destroyed.append('y')
	f = make_populated_factory(
		params={'x': (_ctor_x, dtor_x), 'y': (_ctor_y, dtor_y)},
		deps={'x': (), 'y': ('x',)}
	)
	async def fnc(y): pass
	creation, teardown = f.create_wrappers(fnc)
	context = {}
	await creation(context)
	await teardown(context)
	assert destroyed == ['y', 'x']

@pytest.mark.asyncio
async def testCreateWrappersSkipsAlreadyInContext():
	produced = []
	async def make_x(): produced.append(True); return 'new'
	f = make_populated_factory(
		params={'x': (make_x, None)},
		deps={'x': ()}
	)
	async def fnc(x): pass
	creation, _ = f.create_wrappers(fnc)
	context = {'x': 'existing'}
	await creation(context)
	assert produced == []
	assert context['x'] == 'existing'

@pytest.mark.asyncio
async def testCreateWrappersTearDownClearsContext():
	f = make_populated_factory(
		params={'x': (_ctor_x, None)},
		deps={'x': ()}
	)
	async def fnc(x): pass
	creation, teardown = f.create_wrappers(fnc)
	context = {}
	await creation(context)
	await teardown(context)
	assert 'x' not in context

@pytest.mark.asyncio
async def testCreateWrappersHandlesDiamondDependency():
	produced = []
	async def make_x(): produced.append('x'); return 'x_val'
	async def make_y(x): produced.append('y'); return 'y_val'
	async def make_z(x): produced.append('z'); return 'z_val'
	f = make_populated_factory(
		params={'x': (make_x, None), 'y': (make_y, None), 'z': (make_z, None)},
		deps={'x': (), 'y': ('x',), 'z': ('x',)}
	)
	async def fnc(y, z): pass
	creation, _ = f.create_wrappers(fnc)
	context = {}
	await creation(context)
	assert produced.count('x') == 1

#-------------------------------------------------------------------------------
# produce

@pytest.mark.asyncio
async def testProduceRaisesForUnknownParameter():
	with pytest.raises(ParameterException):
		await make_populated_factory({}, {}).produce('ghost')

@pytest.mark.asyncio
async def testProduceReturnsValue():
	f = make_populated_factory(
		params={'x': (_ctor_x, None)},
		deps={'x': ()}
	)
	assert await f.produce('x') == 'x_val'

@pytest.mark.asyncio
async def testProduceStoresInContext():
	f = make_populated_factory(
		params={'x': (_ctor_x, None)},
		deps={'x': ()}
	)
	ctx = {}
	await f.produce('x', ctx)
	assert ctx['x'] == 'x_val'

@pytest.mark.asyncio
async def testProduceRecursivelyProducesDeps():
	f = make_populated_factory(
		params={'x': (_ctor_x, None), 'y': (_ctor_y, None)},
		deps={'x': (), 'y': ('x',)}
	)
	ctx = {}
	await f.produce('y', ctx)
	assert ctx['x'] == 'x_val'
	assert ctx['y'] == 'y(x_val)'

#-------------------------------------------------------------------------------
# destroy

@pytest.mark.asyncio
async def testDestroyCallsDtor():
	destroyed = []
	async def dtor(val): destroyed.append(val)
	f = make_populated_factory(
		params={'x': (AsyncMock(), dtor)},
		deps={'x': ()}
	)
	await f.destroy('x', 'the_value')
	assert destroyed == ['the_value']

@pytest.mark.asyncio
async def testDestroyNoopWhenNoDtor():
	f = make_populated_factory(
		params={'x': (_ctor_x, None)},
		deps={'x': ()}
	)
	await f.destroy('x', 'val')  # must not raise

@pytest.mark.asyncio
async def testDestroyNoopForUnknownParameter():
	await make_populated_factory({}, {}).destroy('ghost', 'val')  # must not raise

#-------------------------------------------------------------------------------
# shutdown

@pytest.mark.asyncio
async def testShutdownCallsAllSuppliers():
	f = make_factory()
	s1, s2 = MagicMock(), MagicMock()
	s1.shutdown = AsyncMock()
	s2.shutdown = AsyncMock()
	f.suppliers = [s1, s2]
	await f.shutdown()
	s1.shutdown.assert_called_once()
	s2.shutdown.assert_called_once()

@pytest.mark.asyncio
async def testShutdownHandlesNoSuppliers():
	await make_factory().shutdown()  # must not raise

#-------------------------------------------------------------------------------
# prepare_context

@pytest.mark.asyncio
async def testPrepareContextProducesParameter():
	f = make_populated_factory(
		params={'x': (_ctor_x, None)},
		deps={'x': ()}
	)
	async def fnc(x): pass
	ctx = await f.prepare_context(fnc)
	assert ctx['x'] == 'x_val'

@pytest.mark.asyncio
async def testPrepareContextSkipsExistingParameters():
	produced = []
	async def make_x(): produced.append(True); return 'new'
	f = make_populated_factory(
		params={'x': (make_x, None)},
		deps={'x': ()}
	)
	async def fnc(x): pass
	ctx = await f.prepare_context(fnc, {'x': 'existing'})
	assert produced == []
	assert ctx['x'] == 'existing'

@pytest.mark.asyncio
async def testPrepareContextRaisesForUnknownParameter():
	async def fnc(ghost): pass
	with pytest.raises(ParameterException):
		await make_populated_factory({}, {}).prepare_context(fnc)

#-------------------------------------------------------------------------------
# unknown_deps

def testUnknownDepsReturnsNoneWhenAllKnown():
	async def fnc(x): pass
	f = make_populated_factory(
		params={'x': (_ctor_x, None)},
		deps={'x': ()}
	)
	assert f.unknown_deps(fnc) is None

def testUnknownDepsRecognisesBaseParameter():
	async def fnc(request): pass
	assert make_populated_factory({}, {}, base={'request'}).unknown_deps(fnc) is None

def testUnknownDepsReturnsFirstUnknown():
	async def fnc(ghost): pass
	assert make_populated_factory({}, {}).unknown_deps(fnc) == 'ghost'

#-------------------------------------------------------------------------------
# change_base

def testChangeBaseCreatesNewFactory():
	f = make_populated_factory(
		params={'x': (_ctor_x, None)},
		deps={'x': ()},
		base={'old'}
	)
	f2 = f.change_base({'request'})
	assert f2 is not f
	assert f2.base_parameters == {'request'}

def testChangeBaseSharesState():
	f = make_populated_factory(
		params={'x': (_ctor_x, None)},
		deps={'x': ()}
	)
	f2 = f.change_base({'request'})
	assert f2.parameters is f.parameters
	assert f2.dependencies is f.dependencies
	assert f2.suppliers is f.suppliers

#-------------------------------------------------------------------------------

if __name__ == "__main__":
	pytest.main([__file__, "-v"])
