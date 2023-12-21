
SELECT COUNT(*)
	FROM pavao."role" rl
		INNER JOIN pavao."assignment" assig ON assig."role" = rl.id 

	WHERE
		assig.account = $1 AND
		rl."admin";

