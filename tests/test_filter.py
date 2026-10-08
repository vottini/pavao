
import sys
sys.path.append('..')

import pytest
from unittest.mock import MagicMock, AsyncMock
from pavao.filter import RequestFilter, FilterCollection, create_specs

#-------------------------------------------------------------------------------
# helpers

def make_settings(order=None):
	settings = MagicMock()
	settings.get_setting.return_value = order or []
	return settings

def make_factory(unknown=None):
	factory = MagicMock()
	factory.unknown_deps.return_value = unknown
	return factory

@pytest.fixture(autouse=True)
def reset_filter_registry():
	original = RequestFilter.implementations[:]
	yield
	RequestFilter.implementations[:] = original

#-------------------------------------------------------------------------------
# RequestFilter defaults

def testRequestFilterDefaultAllowReturnsTrue():
	class F(RequestFilter): pass
	assert F().allow() is True

def testRequestFilterDefaultEnabledReturnsFalse():
	class F(RequestFilter): pass
	assert F().enabled({}) is False

@pytest.mark.asyncio
async def testRequestFilterDefaultInitIsNoOp():
	class F(RequestFilter): pass
	await F().init({})  # must not raise

def testRequestFilterSubclassIsRegistered():
	before = len(RequestFilter.implementations)
	class F(RequestFilter): pass
	assert len(RequestFilter.implementations) == before + 1

#-------------------------------------------------------------------------------
# create_specs

def testCreateSpecsReturnsClassName():
	class MyFilter(RequestFilter): pass
	name, _, _ = create_specs(MyFilter())
	assert name == 'MyFilter'

def testCreateSpecsEnabledBehavesLikeInstance():
	class MyFilter(RequestFilter):
		def enabled(self, specs): return specs == 'yes'
	instance = MyFilter()
	_, enabled, _ = create_specs(instance)
	assert enabled('yes') is True
	assert enabled('no') is False

def testCreateSpecsAllowBehavesLikeInstance():
	class MyFilter(RequestFilter):
		def allow(self): return False
	_, _, allow = create_specs(MyFilter())
	assert allow() is False

#-------------------------------------------------------------------------------
# FilterCollection.init — filter discovery

@pytest.mark.asyncio
async def testInitLoadsValidFilter():
	class F(RequestFilter): pass
	fc = FilterCollection()
	await fc.init(make_settings(), make_factory())
	names = [name for name, _, _ in fc.list_filters()]
	assert 'F' in names

@pytest.mark.asyncio
async def testInitSkipsFilterWithMissingDep():
	class BadFilter(RequestFilter): pass
	fc = FilterCollection()
	await fc.init(make_settings(), make_factory(unknown='ghost'))
	assert fc.list_filters() == ()

@pytest.mark.asyncio
async def testInitCallsFilterInit():
	called = []
	class F(RequestFilter):
		async def init(self, settings): called.append(True)
	fc = FilterCollection()
	await fc.init(make_settings(), make_factory())
	assert called == [True]

@pytest.mark.asyncio
async def testInitCallsUnknownDepsOnAllow():
	class F(RequestFilter): pass
	factory = make_factory()
	fc = FilterCollection()
	await fc.init(make_settings(), factory)
	factory.unknown_deps.assert_called()

#-------------------------------------------------------------------------------
# FilterCollection.init — ordering

@pytest.mark.asyncio
async def testInitReadsOrderFromSettings():
	class Auth(RequestFilter): pass
	class Rate(RequestFilter): pass
	fc = FilterCollection()
	await fc.init(make_settings(order=['Auth', 'Rate']), make_factory())
	assert fc.ordered_config == ['Auth', 'Rate']

@pytest.mark.asyncio
async def testInitOrderedFiltersComeBefore():
	class Auth(RequestFilter): pass
	class Rate(RequestFilter): pass
	fc = FilterCollection()
	await fc.init(make_settings(order=['Auth']), make_factory())
	names = [name for name, _, _ in fc.list_filters()]
	assert names.index('Auth') < names.index('Rate')

@pytest.mark.asyncio
async def testInitUnknownOrderEntryIsIgnored():
	class F(RequestFilter): pass
	fc = FilterCollection()
	await fc.init(make_settings(order=['NonExistent', 'F']), make_factory())
	names = [name for name, _, _ in fc.list_filters()]
	assert 'F' in names  # must not raise

@pytest.mark.asyncio
async def testInitOrderedFilterNotInUnordered():
	class Auth(RequestFilter): pass
	fc = FilterCollection()
	await fc.init(make_settings(order=['Auth']), make_factory())
	unordered_names = [name for name, _, _ in fc.unordered]
	assert 'Auth' not in unordered_names

@pytest.mark.asyncio
async def testInitEmptyOrderAllFiltersUnordered():
	class A(RequestFilter): pass
	class B(RequestFilter): pass
	fc = FilterCollection()
	await fc.init(make_settings(order=[]), make_factory())
	assert len(fc.ordered_instances) == 0
	assert len(fc.unordered) == 2

#-------------------------------------------------------------------------------
# list_filters

@pytest.mark.asyncio
async def testListFiltersReturnsAllFilters():
	class A(RequestFilter): pass
	class B(RequestFilter): pass
	fc = FilterCollection()
	await fc.init(make_settings(), make_factory())
	assert len(fc.list_filters()) == 2

@pytest.mark.asyncio
async def testListFiltersReturnsTuples():
	class F(RequestFilter): pass
	fc = FilterCollection()
	await fc.init(make_settings(), make_factory())
	for entry in fc.list_filters():
		name, enabled, allow = entry  # must unpack as 3-tuple

@pytest.mark.asyncio
async def testListFiltersEmptyWhenNoFilters():
	fc = FilterCollection()
	await fc.init(make_settings(), make_factory())
	assert fc.list_filters() == ()

#-------------------------------------------------------------------------------

if __name__ == "__main__":
	pytest.main([__file__, "-v"])
