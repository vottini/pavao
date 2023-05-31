
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
	generated = pavao.http.generateToken(original_claims)
	validated_claims = pavao.http.validateToken(generated)
	assert original_claims["iss"] == validated_claims["iss"]

#-------------------------------------------------------------------------------

def testRefresh():
	due_tokens = list()
	due_tokens.append(pavao.http.generateToken(original_claims))
	pavao.http.refresh_secretKey()

	due_tokens.append(pavao.http.generateToken(original_claims))
	pavao.http.refresh_secretKey(timedelta(microseconds=10))
	time.sleep(0.01)

	for due_token in due_tokens:
		assert None == pavao.http.validateToken(due_token)

	good_tokens = list()
	good_tokens.append(pavao.http.generateToken(original_claims))
	pavao.http.refresh_secretKey(5) # 5 days

	good_tokens.append(pavao.http.generateToken(original_claims))
	pavao.http.refresh_secretKey(timedelta(days=5))

	for good_token in good_tokens:
		validated_claims = pavao.http.validateToken(good_token)
		assert original_claims["iss"] == validated_claims["iss"]
	
	assert False == pavao.http.refresh_secretKey("bad argument")
	assert False == pavao.http.refresh_secretKey(32.22)

#-------------------------------------------------------------------------------

def testFrauds():

	bad_tokens = [
		"eyJhbGciOiJIUzI1.eyJzdWIiOiIxMj", # missing signature
		"eyJhbGciOiJIUzI1MiIsInR5cCI6IkpXVCJ9.eyJpYXQiOjE1MTYyMzkwMjJ9.tbDepxpstvGdW8TC3G8zg4B6rUYAOvfzdceoH48wgRQ", # missing kid on header
		"ayJhbGciOiJIUzI1MiIsInR5cCI6IkpXVCJ9.eyJpYXQiOjE1MTYyMzkwMjJ9.tbDepxpstvGdW8TC3G8zg4B6rUYAOvfzdceoH48wgRQ", # bad header json
	]

	for bad_token in bad_tokens:
		assert None == pavao.http.validateToken(bad_token)

	good_token = pavao.http.generateToken(original_claims)
	header, claims, signature = good_token.split('.')

	bad_claims = '{"invalid=323}'
	bad_claims_signature = pavao.http.calcCurrentSignature(header + '.' + bad_claims)
	bad_signature = "a" + signature

	forged_tokens = [
		'.'.join((header, bad_claims, bad_claims_signature)),
		'.'.join((header, claims, bad_signature))
	]

	for forged_token in forged_tokens:
		assert None == pavao.http.validateToken(forged_token)

#-------------------------------------------------------------------------------

if __name__ == "__main__":
	testCreation()
	testRefresh()
	testFrauds()


#token1 = generateToken({"iss": "talaria" })
#print(f"Validated: {validateToken(token1)}")

#print(token1)
#print(_current.ident)
#print(_current.key)
#print(_current.exp)
#
#refresh_secretKey()
#refresh_secretKey(True)
#token2 = generateToken({
#	"iss": "talaria"
#})
#
#print(token2)
#print(_current.ident)
#print(_current.key)
#print(_current.exp)
#
#refresh_secretKey(1)
#token3 = generateToken({
#	"iss": "talaria"
#})
#
#print(token3)
#print(_current.ident)
#print(_current.key)
#print(_current.exp)
#
#refresh_secretKey(timedelta(seconds=5))
#token4 = generateToken({
#	"iss": "talaria"
#})
#
#print(token4)
#print(_current.ident)
#print(_current.key)
#print(_current.exp)
#
#validateToken(token1)
#validateToken(token2)
#validateToken(token3)
#validateToken(token4)
