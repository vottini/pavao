
UPDATE pavao.authentication
	SET
		last_login = NOW(),
		hash = $2
		
	WHERE id = $1;

