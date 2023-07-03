
SELECT
	cls.id AS class_id,
	func.name AS func_name

	FROM pavao.access acs
			INNER JOIN pavao.class cls ON acs.cls = cls.id 
			INNER JOIN pavao.functionality func ON acs.functionality = func.id;

