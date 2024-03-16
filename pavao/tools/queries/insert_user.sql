
INSERT INTO
	pavao.account (login, first_name, last_name)
	VALUES ($1, $2, $3)
	RETURNING id;

