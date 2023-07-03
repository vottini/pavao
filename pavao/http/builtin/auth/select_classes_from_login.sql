
SELECT cls.id
	FROM pavao.account acc
		INNER JOIN pavao.assignment assig ON acc.id = assig.account 
		INNER JOIN pavao.class cls ON assig.cls = cls.id 

	WHERE acc.login = $1;

