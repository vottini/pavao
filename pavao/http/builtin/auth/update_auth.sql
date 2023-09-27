
UPDATE pavao.authentication
	SET hash = $2
	WHERE id = $1;

