
UPDATE pavao.account
	SET last_login = NOW()
	WHERE login = $1;

