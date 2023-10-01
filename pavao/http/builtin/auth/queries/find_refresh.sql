
SELECT
	rt.id AS id,
	rt.expiration AS expiration 

FROM pavao.refresh_token rt
	INNER JOIN pavao.account acc
		ON rt.account = acc.id 

WHERE
	acc.login = $1 AND
	rt.hashed_jti = $2;

