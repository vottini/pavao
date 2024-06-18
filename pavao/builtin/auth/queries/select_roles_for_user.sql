
SELECT rl.id
	FROM pavao.account acc
		INNER JOIN pavao.assignment assig ON acc.id = assig.account
		INNER JOIN pavao."role" rl ON assig."role" = rl.id

	WHERE acc.id = $1;

