
INSERT INTO
	pavao.refresh_token (account, hashed_jti, expiration, access_token)
	SELECT acc.id, $2, $3, $4 from pavao.account acc
		WHERE acc.id = $1;

