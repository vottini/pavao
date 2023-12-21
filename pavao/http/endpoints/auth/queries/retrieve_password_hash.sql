
SELECT auth.hash FROM
	pavao.authentication auth
		INNER JOIN pavao.account acc ON acc.id = auth.account

	WHERE acc.id = $1;

