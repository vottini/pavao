
UPDATE pavao.functionality
	SET enabled = $2
	WHERE id = $1
	RETURNING package, name;

