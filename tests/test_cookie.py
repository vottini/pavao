
import sys
sys.path.append('..')

import pytest
import pavao
from datetime import datetime, timezone

def testCore():
	generated = (pavao.http.Cookie('answer', 42)
		.set_domain('untangle.systems')
		.set_path('/refresh')
		.set_httpOnly()
		.set_expires(datetime.now(timezone.utc))
		.set_sameSite(pavao.http.SameSite.STRICT)
		.set_secure()
	)

	print(generated)

#-------------------------------------------------------------------------------

if __name__ == "__main__":
	testCore()

