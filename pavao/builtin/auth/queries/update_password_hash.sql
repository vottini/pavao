
UPDATE pavao.authentication SET
	hash  = $1,
	needs_change = FALSE
	WHERE account = $2;

