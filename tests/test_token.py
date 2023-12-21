
import sys
sys.path.append('..')

import pytest
import pavao

from datetime import timedelta
import time

original_claims = {
	"iss": "pavao"
}

def testCreation():
	generated = pavao.http.generate_token(original_claims)
	validated_claims = pavao.http.validate_token(generated)
	assert original_claims["iss"] == validated_claims["iss"]

#-------------------------------------------------------------------------------

def testRefresh():
	due_tokens = list()
	due_tokens.append(pavao.http.generate_token(original_claims))
	pavao.http.refresh_secret_key()

	due_tokens.append(pavao.http.generate_token(original_claims))
	pavao.http.refresh_secret_key(timedelta(microseconds=10))
	time.sleep(0.01)

	for due_token in due_tokens:
		assert None == pavao.http.validate_token(due_token)

	good_tokens = list()
	good_tokens.append(pavao.http.generate_token(original_claims))
	pavao.http.refresh_secret_key(5) # 5 days

	good_tokens.append(pavao.http.generate_token(original_claims))
	pavao.http.refresh_secret_key(timedelta(days=5))

	for good_token in good_tokens:
		validated_claims = pavao.http.validate_token(good_token)
		assert original_claims["iss"] == validated_claims["iss"]

	assert False == pavao.http.refresh_secret_key("bad argument")
	assert False == pavao.http.refresh_secret_key(32.22)

#-------------------------------------------------------------------------------

def testFrauds():

	bad_tokens = [
		"eyJhbGciOiJIUzI1.eyJzdWIiOiIxMj", # missing signature
		"eyJhbGciOiJIUzI1MiIsInR5cCI6IkpXVCJ9.eyJpYXQiOjE1MTYyMzkwMjJ9.tbDepxpstvGdW8TC3G8zg4B6rUYAOvfzdceoH48wgRQ", # missing kid on header
		"ayJhbGciOiJIUzI1MiIsInR5cCI6IkpXVCJ9.eyJpYXQiOjE1MTYyMzkwMjJ9.tbDepxpstvGdW8TC3G8zg4B6rUYAOvfzdceoH48wgRQ", # bad header json
	]

	for bad_token in bad_tokens:
		assert None == pavao.http.validate_token(bad_token)

	good_token = pavao.http.generate_token(original_claims)
	header, claims, signature = good_token.split('.')

	bad_claims = '{"invalid=323}'
	bad_claims_signature = pavao.http.calc_current_signature(header + '.' + bad_claims)
	bad_signature = "a" + signature

	forged_tokens = [
		'.'.join((header, bad_claims, bad_claims_signature)),
		'.'.join((header, claims, bad_signature))
	]

	for forged_token in forged_tokens:
		assert None == pavao.http.validate_token(forged_token)

#-------------------------------------------------------------------------------

if __name__ == "__main__":
	testCreation()
	testRefresh()
	testFrauds()


#token1 = generate_token({"iss": "talaria" })
#print(f"Validated: {validate_token(token1)}")

#print(token1)
#print(_current.ident)
#print(_current.key)
#print(_current.exp)
#
#refresh_secret_key()
#refresh_secret_key(True)
#token2 = generate_token({
#	"iss": "talaria"
#})
#
#print(token2)
#print(_current.ident)
#print(_current.key)
#print(_current.exp)
#
#refresh_secret_key(1)
#token3 = generate_token({
#	"iss": "talaria"
#})
#
#print(token3)
#print(_current.ident)
#print(_current.key)
#print(_current.exp)
#
#refresh_secret_key(timedelta(seconds=5))
#token4 = generate_token({
#	"iss": "talaria"
#})
#
#print(token4)
#print(_current.ident)
#print(_current.key)
#print(_current.exp)
#
#validate_token(token1)
#validate_token(token2)
#validate_token(token3)
#validate_token(token4)
