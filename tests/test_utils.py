
import sys
sys.path.append('..')

import pytest
from pavao.utils import deduce_parameters, adapter, async_adapter, silent_generator, remove_prefix, WrappedFunction

#-------------------------------------------------------------------------------
# deduce_parameters

def testDeduceSimpleFunction():
	def fn(a, b, c): pass
	assert deduce_parameters(fn) == ('a', 'b', 'c')

def testDeduceNoParams():
	def fn(): pass
	assert deduce_parameters(fn) == ()

def testDeduceBoundMethodSkipsSelf():
	class MyClass:
		def method(self, x, y): pass
	assert deduce_parameters(MyClass().method) == ('x', 'y')

def testDeduceAsyncFunction():
	async def fn(x, y): pass
	assert deduce_parameters(fn) == ('x', 'y')

def testDeduceIgnoresLocals():
	def fn(a):
		local_var = 1
	assert deduce_parameters(fn) == ('a',)

#-------------------------------------------------------------------------------
# remove_prefix

def testRemovePrefixMatch():
	assert remove_prefix("/api/users", "/api") == "/users"

def testRemovePrefixNoMatch():
	assert remove_prefix("/other/path", "/api") == "/other/path"

def testRemovePrefixEmptyPrefix():
	assert remove_prefix("hello", "") == "hello"

def testRemovePrefixExactMatch():
	assert remove_prefix("/api", "/api") == ""

#-------------------------------------------------------------------------------
# adapter

@pytest.mark.asyncio
async def testAdapterWrapsAsyncFunction():
	async def fn(x, y): return x + y
	wrapped = adapter(fn)
	result = await wrapped({'x': 1, 'y': 2})
	assert result == 3

@pytest.mark.asyncio
async def testAdapterWrapsSyncFunction():
	def fn(x, y): return x + y
	wrapped = adapter(fn)
	result = wrapped({'x': 3, 'y': 4})
	assert result == 7

@pytest.mark.asyncio
async def testAdapterWrapAsCoroutineFalse():
	async def fn(x): return x * 2
	wrapped = adapter(fn, wrap_as_coroutine=False)
	result = wrapped({'x': 5})
	# returns a coroutine, not the value
	import inspect
	assert inspect.iscoroutine(result)
	await result

def testAdapterSelectsCorrectParams():
	def fn(a, c): return a + c
	wrapped = adapter(fn)
	result = wrapped({'a': 1, 'b': 99, 'c': 2})
	assert result == 3

#-------------------------------------------------------------------------------
# async_adapter

@pytest.mark.asyncio
async def testAsyncAdapterWrapsSync():
	def fn(): return 42
	wrapped = async_adapter(fn)
	result = await wrapped()
	assert result == 42

@pytest.mark.asyncio
async def testAsyncAdapterPassesThroughAsync():
	async def fn(): return 99
	wrapped = async_adapter(fn)
	assert wrapped is fn

#-------------------------------------------------------------------------------
# silent_generator

@pytest.mark.asyncio
async def testSilentGeneratorYieldsNone():
	async def fn(x): pass
	gen_fn = silent_generator(fn)
	results = [v async for v in gen_fn(x=1)]
	assert results == [None]

@pytest.mark.asyncio
async def testSilentGeneratorCallsOriginal():
	called_with = {}
	async def fn(x, y):
		called_with['x'] = x
		called_with['y'] = y

	gen_fn = silent_generator(fn)
	async for _ in gen_fn(x=10, y=20):
		pass

	assert called_with == {'x': 10, 'y': 20}

def testSilentGeneratorPreservesDIParams():
	async def fn(request, response): pass
	gen_fn = silent_generator(fn)
	assert deduce_parameters(gen_fn) == ('request', 'response')

#-------------------------------------------------------------------------------
# WrappedFunction

@pytest.mark.asyncio
async def testWrappedFunctionCallsProcessor():
	async def processor(ctx): return ctx['x'] * 2
	wf = WrappedFunction(None, processor, None)
	result = await wf({'x': 5})
	assert result == 10

@pytest.mark.asyncio
async def testWrappedFunctionCallsPreAndPost():
	order = []
	async def pre(ctx): order.append('pre')
	async def processor(ctx): order.append('proc')
	async def post(ctx): order.append('post')
	wf = WrappedFunction(pre, processor, post)
	await wf({})
	assert order == ['pre', 'proc', 'post']

@pytest.mark.asyncio
async def testWrappedFunctionPostRunsOnException():
	post_called = []
	async def pre(ctx): pass
	async def processor(ctx): raise ValueError("boom")
	async def post(ctx): post_called.append(True)
	wf = WrappedFunction(pre, processor, post)
	with pytest.raises(ValueError):
		await wf({})
	assert post_called

@pytest.mark.asyncio
async def testWrappedFunctionNonePreSkipsIt():
	async def processor(ctx): return 'done'
	wf = WrappedFunction(None, processor, None)
	result = await wf({})
	assert result == 'done'

#-------------------------------------------------------------------------------

if __name__ == "__main__":
	pytest.main([__file__, "-v"])
