
import sys
sys.path.append('..')

import pytest
import base64
import json

from datetime import timedelta
from pavao.jwt import JwtSupplier

#-------------------------------------------------------------------------------

@pytest.fixture
def supplier():
	return JwtSupplier()

claims = {"iss": "pavao", "sub": "user1"}

#-------------------------------------------------------------------------------
# generate / validate round-trip

def testGenerateValidateRoundTrip(supplier):
	token = supplier.generate_token(claims)
	result = supplier.validate_token(token)
	assert result["iss"] == "pavao"
	assert result["sub"] == "user1"

def testTokenHasThreeParts(supplier):
	token = supplier.generate_token(claims)
	assert token.count('.') == 2

def testHeaderContainsKidAndAlg(supplier):
	token = supplier.generate_token(claims)
	header_b64 = token.split('.')[0]
	header = json.loads(base64.urlsafe_b64decode(header_b64 + "==="))
	assert header["alg"] == "HS256"
	assert header["kid"] == supplier.current_key.ident

#-------------------------------------------------------------------------------
# validate_token: structural rejections

def testValidateMissingSegmentReturnsNone(supplier):
	assert supplier.validate_token("only.two") is None

def testValidateTooManySegmentsReturnsNone(supplier):
	assert supplier.validate_token("a.b.c.d") is None

def testValidateBadBase64HeaderReturnsNone(supplier):
	assert supplier.validate_token("!!!.eyJpc3MiOiJ4In0.abc") is None

def testValidateWrongAlgReturnsNone(supplier):
	header = base64.urlsafe_b64encode(b'{"alg":"RS256","typ":"JWT","kid":"x"}').decode().strip('=')
	payload = base64.urlsafe_b64encode(b'{}').decode().strip('=')
	assert supplier.validate_token(f"{header}.{payload}.fakesig") is None

def testValidateMissingKidReturnsNone(supplier):
	header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').decode().strip('=')
	payload = base64.urlsafe_b64encode(b'{}').decode().strip('=')
	assert supplier.validate_token(f"{header}.{payload}.fakesig") is None

def testValidateUnknownKidReturnsNone(supplier):
	header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT","kid":"unknown"}').decode().strip('=')
	payload = base64.urlsafe_b64encode(b'{}').decode().strip('=')
	assert supplier.validate_token(f"{header}.{payload}.fakesig") is None

def testValidateTamperedSignatureReturnsNone(supplier):
	token = supplier.generate_token(claims)
	header, payload, sig = token.split('.')
	bad_sig = ("b" if sig[0] == "a" else "a") + sig[1:]
	assert supplier.validate_token(f"{header}.{payload}.{bad_sig}") is None

def testValidateTamperedPayloadReturnsNone(supplier):
	token = supplier.generate_token(claims)
	header, _, sig = token.split('.')
	bad_payload = base64.urlsafe_b64encode(b'{"iss":"evil"}').decode().strip('=')
	assert supplier.validate_token(f"{header}.{bad_payload}.{sig}") is None

def testValidateBadPayloadJsonReturnsNone(supplier):
	token = supplier.generate_token(claims)
	header, _, _ = token.split('.')
	bad_payload = base64.urlsafe_b64encode(b'{bad json}').decode().strip('=')
	forged_sig = supplier._calc_signature(f"{header}.{bad_payload}")
	assert supplier.validate_token(f"{header}.{bad_payload}.{forged_sig}") is None

#-------------------------------------------------------------------------------
# refresh_secret_key

def testRefreshInvalidatesOldToken(supplier):
	token = supplier.generate_token(claims)
	supplier.refresh_secret_key()
	assert supplier.validate_token(token) is None

def testRefreshWithPastValidityKeepsOldTokenValid(supplier):
	token = supplier.generate_token(claims)
	supplier.refresh_secret_key(previous_validity=5)  # 5 days
	result = supplier.validate_token(token)
	assert result is not None
	assert result["iss"] == "pavao"

def testRefreshWithTimedeltaPastValidity(supplier):
	token = supplier.generate_token(claims)
	supplier.refresh_secret_key(previous_validity=timedelta(days=5))
	assert supplier.validate_token(token) is not None

def testRefreshNewTokenValidAfterRefresh(supplier):
	supplier.refresh_secret_key()
	token = supplier.generate_token(claims)
	assert supplier.validate_token(token) is not None

def testRefreshExpiredPastKeyInvalidatesToken(supplier):
	import time
	token = supplier.generate_token(claims)
	supplier.refresh_secret_key(previous_validity=timedelta(microseconds=1))
	time.sleep(0.01)
	assert supplier.validate_token(token) is None

def testRefreshExpiredPastKeyRemovedOnNextRefresh(supplier):
	import time
	token = supplier.generate_token(claims)
	supplier.refresh_secret_key(previous_validity=timedelta(microseconds=1))
	time.sleep(0.01)
	supplier.refresh_secret_key()
	assert len(supplier.past_keys) == 0

def testRefreshNoPastValidityDropsPreviousKey(supplier):
	token = supplier.generate_token(claims)
	supplier.refresh_secret_key()
	assert supplier.validate_token(token) is None
	assert len(supplier.past_keys) == 0

def testRefreshBadStringArgumentReturnsFalse(supplier):
	assert supplier.refresh_secret_key(previous_validity="bad") is False

def testRefreshBadFloatArgumentReturnsFalse(supplier):
	assert supplier.refresh_secret_key(previous_validity=3.14) is False

def testRefreshZeroIntArgumentReturnsFalse(supplier):
	assert supplier.refresh_secret_key(previous_validity=0) is False

def testRefreshNegativeIntArgumentReturnsFalse(supplier):
	assert supplier.refresh_secret_key(previous_validity=-1) is False

def testRefreshNegativeTimedeltaReturnsFalse(supplier):
	assert supplier.refresh_secret_key(previous_validity=timedelta(days=-1)) is False

def testRefreshZeroTimedeltaReturnsFalse(supplier):
	assert supplier.refresh_secret_key(previous_validity=timedelta(0)) is False

def testRefreshReturnsTrueOnSuccess(supplier):
	assert supplier.refresh_secret_key() is True
	assert supplier.refresh_secret_key(previous_validity=1) is True

#-------------------------------------------------------------------------------
# multiple refreshes / key rotation

def testMultipleRefreshesWithValidity(supplier):
	t1 = supplier.generate_token({"n": 1})
	supplier.refresh_secret_key(previous_validity=timedelta(days=1))
	t2 = supplier.generate_token({"n": 2})
	supplier.refresh_secret_key(previous_validity=timedelta(days=1))
	t3 = supplier.generate_token({"n": 3})

	assert supplier.validate_token(t1) is not None
	assert supplier.validate_token(t2) is not None
	assert supplier.validate_token(t3) is not None

def testRefreshWithoutValidityDoesNotAddPreviousKey(supplier):
	supplier.refresh_secret_key()
	assert len(supplier.past_keys) == 0

	supplier.refresh_secret_key(previous_validity=timedelta(days=1))
	prev_count = len(supplier.past_keys)
	supplier.refresh_secret_key()
	# previous key not added; valid past keys are kept
	assert len(supplier.past_keys) == prev_count

#-------------------------------------------------------------------------------

if __name__ == "__main__":
	pytest.main([__file__, "-v"])
