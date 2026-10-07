
import sys
sys.path.append('..')

import pytest
from unittest.mock import MagicMock
from pavao.parameters import accepts_parameters
from pavao.exception import PavaoException

#-------------------------------------------------------------------------------

def make_request(params):
	req = MagicMock()
	req.params = params
	req.parse_locale_priority.return_value = []
	return req

def make_response():
	res = MagicMock()
	res.status = 200
	return res

#-------------------------------------------------------------------------------
# decorator-time validation

def testBadListSpecEmptyRaises():
	with pytest.raises(PavaoException):
		accepts_parameters({"x": []})

def testBadListSpecMultipleElementsRaises():
	with pytest.raises(PavaoException):
		accepts_parameters({"x": [str, int]})

def testBadListSpecNonTypeElementRaises():
	with pytest.raises(PavaoException):
		accepts_parameters({"x": ["not a type"]})

def testValidSpecDoesNotRaise():
	accepts_parameters({"x": str})
	accepts_parameters({"x": int})
	accepts_parameters({"x": "default"})
	accepts_parameters({"x": [int]})

#-------------------------------------------------------------------------------
# required parameters

@pytest.mark.asyncio
async def testRequiredParamPresent():
	@accepts_parameters({"name": str})
	async def endpoint(parameters, request, response):
		return parameters["name"]

	req = make_request({"name": "alice"})
	result = await endpoint(request=req, response=make_response())
	assert result == "alice"

@pytest.mark.asyncio
async def testRequiredParamMissingReturns400():
	@accepts_parameters({"name": str})
	async def endpoint(parameters, request, response):
		return parameters["name"]

	res = make_response()
	await endpoint(request=make_request({}), response=res)
	res.set_status.assert_called_with(400)

@pytest.mark.asyncio
async def testRequiredParamMissingReturnsNone():
	@accepts_parameters({"name": str})
	async def endpoint(parameters, request, response):
		return parameters["name"]

	result = await endpoint(request=make_request({}), response=make_response())
	assert result is None

#-------------------------------------------------------------------------------
# optional parameters (with defaults)

@pytest.mark.asyncio
async def testOptionalParamUsesDefault():
	@accepts_parameters({"page": 1})
	async def endpoint(parameters, request, response):
		return parameters["page"]

	result = await endpoint(request=make_request({}), response=make_response())
	assert result == 1

@pytest.mark.asyncio
async def testOptionalParamOverriddenByRequest():
	@accepts_parameters({"page": 1})
	async def endpoint(parameters, request, response):
		return parameters["page"]

	result = await endpoint(request=make_request({"page": "3"}), response=make_response())
	assert result == 3

#-------------------------------------------------------------------------------
# type coercion

@pytest.mark.asyncio
async def testIntCoercion():
	@accepts_parameters({"count": int})
	async def endpoint(parameters, request, response):
		return parameters["count"]

	result = await endpoint(request=make_request({"count": "42"}), response=make_response())
	assert result == 42

@pytest.mark.asyncio
async def testInvalidTypeReturns400():
	@accepts_parameters({"count": int})
	async def endpoint(parameters, request, response):
		return parameters["count"]

	res = make_response()
	await endpoint(request=make_request({"count": "notanint"}), response=res)
	res.set_status.assert_called_with(400)

@pytest.mark.asyncio
async def testInvalidTypeReturnsNone():
	@accepts_parameters({"count": int})
	async def endpoint(parameters, request, response):
		return parameters["count"]

	result = await endpoint(request=make_request({"count": "notanint"}), response=make_response())
	assert result is None

#-------------------------------------------------------------------------------
# list parameters

@pytest.mark.asyncio
async def testListParam():
	@accepts_parameters({"ids": [int]})
	async def endpoint(parameters, request, response):
		return parameters["ids"]

	result = await endpoint(request=make_request({"ids": "1,2,3"}), response=make_response())
	assert result == [1, 2, 3]

@pytest.mark.asyncio
async def testListParamSingleElement():
	@accepts_parameters({"ids": [int]})
	async def endpoint(parameters, request, response):
		return parameters["ids"]

	result = await endpoint(request=make_request({"ids": "7"}), response=make_response())
	assert result == [7]

@pytest.mark.asyncio
async def testListParamMissingReturns400():
	@accepts_parameters({"ids": [int]})
	async def endpoint(parameters, request, response):
		return parameters["ids"]

	res = make_response()
	await endpoint(request=make_request({}), response=res)
	res.set_status.assert_called_with(400)

@pytest.mark.asyncio
async def testListParamInvalidElementReturns400():
	@accepts_parameters({"ids": [int]})
	async def endpoint(parameters, request, response):
		return parameters["ids"]

	res = make_response()
	await endpoint(request=make_request({"ids": "1,bad,3"}), response=res)
	res.set_status.assert_called_with(400)

#-------------------------------------------------------------------------------
# multiple parameters

@pytest.mark.asyncio
async def testMultipleParams():
	@accepts_parameters({"name": str, "age": int})
	async def endpoint(parameters, request, response):
		return parameters

	result = await endpoint(
		request=make_request({"name": "bob", "age": "30"}),
		response=make_response())
	assert result == {"name": "bob", "age": 30}

@pytest.mark.asyncio
async def testMixedRequiredAndOptional():
	@accepts_parameters({"name": str, "page": 1})
	async def endpoint(parameters, request, response):
		return parameters

	result = await endpoint(
		request=make_request({"name": "alice"}),
		response=make_response())
	assert result == {"name": "alice", "page": 1}

#-------------------------------------------------------------------------------
# wrapper preserves injectable parameter names

def testWrappedFunctionDeclaresDIParams():
	@accepts_parameters({"x": str})
	async def endpoint(parameters, request, response):
		pass

	import pavao.utils as utils
	params = utils.deduce_parameters(endpoint)
	assert "request" in params
	assert "response" in params

#-------------------------------------------------------------------------------

if __name__ == "__main__":
	pytest.main([__file__, "-v"])
