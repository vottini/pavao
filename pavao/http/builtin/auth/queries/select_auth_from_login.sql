
SELECT acc.id, auth.id, acc.active, auth.hash, auth.needs_change 
	FROM pavao.authentication auth INNER JOIN pavao.account acc
		ON acc.id = auth.account 

	WHERE acc.login = $1;

