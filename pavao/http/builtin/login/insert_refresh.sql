
INSERT INTO
	pavao.refresh_token (account, hashed_jti, expiry)
	SELECT acc.id, $2, $3 from pavao.account acc
		WHERE acc.login = $1;

