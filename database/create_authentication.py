#!/usr/bin/env python

import sys
from argon2 import PasswordHasher

if len(sys.argv) < 3:
	print(f"Usage {sys.argv[0]} <login> <password>")
	sys.exit(0)

_, login, password = sys.argv
passwordHash = PasswordHasher().hash(password)

insertAuthentication = f"""

INSERT INTO
	pavao.authentication (
		account,
		hash,
		needs_change)

	SELECT
		id,
		'{passwordHash}',
		FALSE

	FROM pavao.account
	WHERE login = '{login}';

"""

print(insertAuthentication)

