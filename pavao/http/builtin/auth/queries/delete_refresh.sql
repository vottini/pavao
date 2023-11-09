
DELETE FROM pavao.refresh_token 
	WHERE id IN (
		SELECT rt.id FROM pavao.refresh_token rt
			INNER JOIN pavao.account acc ON acc.id = rt.account 
			WHERE acc.id = $1 AND rt.access_token = $2);

