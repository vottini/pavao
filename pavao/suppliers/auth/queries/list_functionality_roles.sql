
SELECT rl.id
	FROM pavao.access acs
		INNER JOIN pavao."role" rl ON acs."role" = rl.id
		INNER JOIN pavao.functionality func
			ON acs.functionality = func.id

	WHERE func.name = $1;

