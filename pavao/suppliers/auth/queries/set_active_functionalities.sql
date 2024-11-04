
UPDATE pavao.functionality
	SET active = (id = ANY($1::INTEGER[]));

