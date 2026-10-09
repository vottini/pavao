
import sys
sys.path.append('..')

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock, patch

from pavao.json import (
	_load_blueprint, _trial_predicate, _warn_unused,
	_valid_content_types,
	accepts_json, generates_json,
	error_blueprint, error_contents,
	field_present
)
from pavao.exception import PavaoException

#-------------------------------------------------------------------------------
# helpers

simple_schema = 'root { name: String }'

def make_request(content_type='application/json'):
	req = MagicMock()
	req.headers.get.return_value = content_type
	return req

def make_response(status=200):
	resp = MagicMock()
	resp.status = status
	return resp

def make_receive(body=b'', more_body=False):
	return AsyncMock(return_value={'body': body, 'more_body': more_body})

#-------------------------------------------------------------------------------
# _valid_content_types regression (missing comma bug)

def testValidContentTypesHasTwoElements():
	assert len(_valid_content_types) == 2

def testValidContentTypesContainsApplicationJson():
	assert 'application/json' in _valid_content_types

def testValidContentTypesContainsApplicationJsonWithCharset():
	assert 'application/json; charset=utf-8' in _valid_content_types

#-------------------------------------------------------------------------------
# _load_blueprint

def testLoadBlueprintRaisesWhenNeitherStringNorFile():
	with pytest.raises(PavaoException):
		_load_blueprint(None, None)

def testLoadBlueprintWarnsAndUsesStringWhenBothGiven():
	with patch('pavao.json.Logger') as mock_logger:
		bp = _load_blueprint(simple_schema, 'some_file.json')
	mock_logger.warning.assert_called_once()
	assert bp is not None

def testLoadBlueprintLoadsFromString():
	bp = _load_blueprint(simple_schema, None)
	ok, result = bp.deserialize('{"name": "hello"}')
	assert ok
	assert result['name'] == 'hello'

def testLoadBlueprintLoadsFromFile(tmp_path):
	f = tmp_path / 'schema.json'
	f.write_text(simple_schema)
	bp = _load_blueprint(None, str(f))
	ok, result = bp.deserialize('{"name": "hello"}')
	assert ok

def testLoadBlueprintChoosesRoot():
	with patch('pavao.json.jsonbp') as mock_jsonbp:
		mock_bp = MagicMock()
		mock_jsonbp.load_string.return_value = mock_bp
		_load_blueprint(simple_schema, None, root='item')
	mock_bp.choose_root.assert_called_once_with('item', False, 0, 1024)

#-------------------------------------------------------------------------------
# _trial_predicate

def testTrialPredicatePassesForValidPredicate():
	_trial_predicate(lambda status: status == 200)

def testTrialPredicateRaisesForBrokenPredicate():
	with pytest.raises(PavaoException):
		_trial_predicate(lambda status: status + "broken")

#-------------------------------------------------------------------------------
# _warn_unused

def testWarnUnusedWarnsWhenCandidatePresent():
	with patch('pavao.json.Logger') as mock_logger:
		_warn_unused({'status': 200, 'predicate': lambda s: True}, 'predicate', ['status'])
	mock_logger.warning.assert_called_once()
	assert 'status' in mock_logger.warning.call_args.args[0]

def testWarnUnusedSilentWhenCandidateAbsent():
	with patch('pavao.json.Logger') as mock_logger:
		_warn_unused({'predicate': lambda s: True}, 'predicate', ['status'])
	mock_logger.warning.assert_not_called()

#-------------------------------------------------------------------------------
# accepts_json wrapper

@pytest.mark.asyncio
async def testAcceptsJsonRejects400WhenContentTypeMissing():
	@accepts_json(string_blueprint=simple_schema)
	async def ep(parsed_json): return None

	request = make_request(content_type=None)
	response = make_response()
	await ep(request=request, response=response, receive=make_receive())

	response.set_status.assert_called_once_with(400)
	response.set_content.assert_called_once()
	assert response.set_content.call_args.args[0] == 'application/json'


@pytest.mark.asyncio
async def testAcceptsJsonRejects400WhenContentTypeWrong():
	@accepts_json(string_blueprint=simple_schema)
	async def ep(parsed_json): return None

	request = make_request(content_type='text/plain')
	response = make_response()
	await ep(request=request, response=response, receive=make_receive())

	response.set_status.assert_called_once_with(400)
	response.set_content.assert_called_once()


@pytest.mark.asyncio
async def testAcceptsJsonRejects400OnDecodeError():
	@accepts_json(string_blueprint=simple_schema)
	async def ep(parsed_json): return None

	request = make_request()
	response = make_response()
	receive = make_receive(body=b'\xff\xfe')  # invalid utf-8

	with patch('pavao.json.Logger'):
		await ep(request=request, response=response, receive=receive)

	response.set_status.assert_called_with(400)
	response.set_content.assert_called_once()


@pytest.mark.asyncio
async def testAcceptsJsonRejects400OnDeserializationFailure():
	@accepts_json(string_blueprint=simple_schema)
	async def ep(parsed_json): return None

	request = make_request()
	response = make_response()
	receive = make_receive(body=b'{"wrong_field": 123}')

	await ep(request=request, response=response, receive=receive)

	response.set_status.assert_called_with(400)
	response.set_content.assert_called_once()


@pytest.mark.asyncio
async def testAcceptsJsonPassesParsedJsonToFunction():
	received = []

	@accepts_json(string_blueprint=simple_schema)
	async def ep(parsed_json):
		received.append(parsed_json)
		return None

	request = make_request()
	response = make_response()
	receive = make_receive(body=b'{"name": "hello"}')

	await ep(request=request, response=response, receive=receive)

	assert len(received) == 1
	assert received[0].name == 'hello'


@pytest.mark.asyncio
async def testAcceptsJsonAcceptsCharsetContentType():
	received = []

	@accepts_json(string_blueprint=simple_schema)
	async def ep(parsed_json):
		received.append(parsed_json)
		return None

	request = make_request(content_type='application/json; charset=utf-8')
	response = make_response()
	receive = make_receive(body=b'{"name": "hello"}')

	await ep(request=request, response=response, receive=receive)

	assert len(received) == 1


@pytest.mark.asyncio
async def testAcceptsJsonAssemblesMultiChunkBody():
	received = []

	@accepts_json(string_blueprint=simple_schema)
	async def ep(parsed_json):
		received.append(parsed_json)
		return None

	request = make_request()
	response = make_response()
	chunks = [
		{'body': b'{"name":', 'more_body': True},
		{'body': b'"hello"}', 'more_body': False},
	]
	receive = AsyncMock(side_effect=chunks)

	await ep(request=request, response=response, receive=receive)

	assert received[0].name == 'hello'


@pytest.mark.asyncio
async def testAcceptsJsonPassesResponseWhenDeclared():
	received_response = []

	@accepts_json(string_blueprint=simple_schema)
	async def ep(parsed_json, response):
		received_response.append(response)
		return None

	request = make_request()
	response = make_response()
	receive = make_receive(body=b'{"name": "hi"}')

	await ep(request=request, response=response, receive=receive)

	assert received_response[0] is response


@pytest.mark.asyncio
async def testAcceptsJsonAllParamsRegressionWhenFunctionDeclaresRequest():
	# regression: all_params precedence fix — request must not be dropped
	# when declared in the function signature
	received_request = []

	@accepts_json(string_blueprint=simple_schema)
	async def ep(parsed_json, request):
		received_request.append(request)
		return None

	request = make_request()
	response = make_response()
	receive = make_receive(body=b'{"name": "hi"}')

	await ep(request=request, response=response, receive=receive)

	assert received_request[0] is request

#-------------------------------------------------------------------------------
# generates_json — no dispatchers (default blueprint path)

@pytest.mark.asyncio
async def testGeneratesJsonSerializesPayloadForNonErrorStatus():
	@generates_json(string_blueprint=simple_schema)
	async def ep(): return {'name': 'hello'}

	response = make_response(status=200)
	await ep(response=response)

	response.set_content.assert_called_once()
	args = response.set_content.call_args.args
	assert args[0] == 'application/json'
	assert b'hello' in args[1]


@pytest.mark.asyncio
async def testGeneratesJsonSerializesErrorBlueprintForErrorStatus():
	@generates_json(string_blueprint=simple_schema)
	async def ep(): return {'error': 'E', 'description': 'D', 'timestamp': datetime.now(timezone.utc)}

	response = make_response(status=400)
	await ep(response=response)

	response.set_content.assert_called_once()


@pytest.mark.asyncio
async def testGeneratesJsonReturnsEarlyWhenPayloadIsNone():
	@generates_json(string_blueprint=simple_schema)
	async def ep(): return None

	response = make_response(status=200)
	await ep(response=response)

	response.set_content.assert_not_called()


@pytest.mark.asyncio
async def testGeneratesJsonSets500WhenNoDispatcherMatches():
	@generates_json(dispatchers=[
		{'string': simple_schema, 'status': 200}
	])
	async def ep(): return {'name': 'hello'}

	response = make_response(status=204)
	await ep(response=response)

	response.set_status.assert_called_with(500)

#-------------------------------------------------------------------------------
# generates_json — with dispatchers

@pytest.mark.asyncio
async def testGeneratesJsonDispatchesByPredicate():
	@generates_json(dispatchers=[
		{'string': simple_schema, 'predicate': lambda s: s == 201}
	])
	async def ep(): return {'name': 'created'}

	response = make_response(status=201)
	await ep(response=response)

	response.set_content.assert_called_once()
	assert b'created' in response.set_content.call_args.args[1]


@pytest.mark.asyncio
async def testGeneratesJsonDispatchesByStatuses():
	@generates_json(dispatchers=[
		{'string': simple_schema, 'statuses': {200, 201}}
	])
	async def ep(): return {'name': 'ok'}

	response = make_response(status=201)
	await ep(response=response)

	response.set_content.assert_called_once()


@pytest.mark.asyncio
async def testGeneratesJsonDispatchesByStatus():
	@generates_json(dispatchers=[
		{'string': simple_schema, 'status': 200}
	])
	async def ep(): return {'name': 'ok'}

	response = make_response(status=200)
	await ep(response=response)

	response.set_content.assert_called_once()


@pytest.mark.asyncio
async def testGeneratesJsonStatusesClosureRegressionTwoRules():
	# regression: lambda closure — each rule must match only its own statuses
	schema2 = 'root { value: Integer }'
	dispatched = []

	@generates_json(dispatchers=[
		{'string': simple_schema, 'statuses': {200}},
		{'string': schema2,       'statuses': {201}},
	])
	async def ep(): return None

	# status 201 must not match the first rule
	response_200 = make_response(status=200)
	response_201 = make_response(status=201)

	@generates_json(dispatchers=[
		{'string': simple_schema, 'statuses': {200}},
		{'string': schema2,       'statuses': {201}},
	])
	async def ep_200(): return {'name': 'ok'}

	@generates_json(dispatchers=[
		{'string': simple_schema, 'statuses': {200}},
		{'string': schema2,       'statuses': {201}},
	])
	async def ep_201(): return {'value': 42}

	await ep_200(response=response_200)
	await ep_201(response=response_201)

	# each should have been called exactly once with the right content
	assert response_200.set_content.call_count == 1
	assert response_201.set_content.call_count == 1
	assert b'ok' in response_200.set_content.call_args.args[1]
	assert b'42' in response_201.set_content.call_args.args[1]


@pytest.mark.asyncio
async def testGeneratesJsonStatusClosureRegressionTwoRules():
	# regression: lambda closure — each status rule must match only its own value
	schema2 = 'root { value: Integer }'

	@generates_json(dispatchers=[
		{'string': simple_schema, 'status': 200},
		{'string': schema2,       'status': 201},
	])
	async def ep_200(): return {'name': 'ok'}

	@generates_json(dispatchers=[
		{'string': simple_schema, 'status': 200},
		{'string': schema2,       'status': 201},
	])
	async def ep_201(): return {'value': 42}

	response_200 = make_response(status=200)
	response_201 = make_response(status=201)

	await ep_200(response=response_200)
	await ep_201(response=response_201)

	assert b'ok' in response_200.set_content.call_args.args[1]
	assert b'42' in response_201.set_content.call_args.args[1]

#-------------------------------------------------------------------------------
# generates_json — dispatcher validation

@pytest.mark.asyncio
async def testGeneratesJsonReusesErrorBlueprintForErrorContentsDispatcher():
	# when a dispatcher rule uses error_contents string, it should reuse error_blueprint
	@generates_json(dispatchers=[
		{'string': error_contents, 'status': 200}
	])
	async def ep(): return {'error': 'E', 'description': 'D', 'timestamp': datetime.now(timezone.utc)}

	response = make_response(status=200)
	await ep(response=response)

	response.set_content.assert_called_once()


def testGeneratesJsonRaisesWhenNoPredicate():
	with pytest.raises(PavaoException):
		@generates_json(dispatchers=[{'string': simple_schema}])
		async def ep(): pass


def testGeneratesJsonRaisesWhenDispatchersNotIterable():
	with pytest.raises(PavaoException):
		@generates_json(dispatchers=42)
		async def ep(): pass


def testGeneratesJsonWarnsWhenPredicateAndStatusesBothSpecified():
	with patch('pavao.json.Logger') as mock_logger:
		@generates_json(dispatchers=[{
			'string': simple_schema,
			'predicate': lambda s: True,
			'statuses': {200}
		}])
		async def ep(): pass
	mock_logger.warning.assert_called()


def testGeneratesJsonWarnsWhenStatusesAndStatusBothSpecified():
	with patch('pavao.json.Logger') as mock_logger:
		@generates_json(dispatchers=[{
			'string': simple_schema,
			'statuses': {200},
			'status': 200
		}])
		async def ep(): pass
	mock_logger.warning.assert_called()

#-------------------------------------------------------------------------------
# field_present

def testFieldPresentReturnsTrueWhenPresent():
	import umapper
	obj = umapper.convert_to_object({'name': 'hello'})
	assert field_present(obj, 'name') is True

def testFieldPresentReturnsFalseWhenAbsent():
	import umapper
	obj = umapper.convert_to_object({'name': 'hello'})
	assert field_present(obj, 'missing') is False

#-------------------------------------------------------------------------------

if __name__ == "__main__":
	pytest.main([__file__, "-v"])
