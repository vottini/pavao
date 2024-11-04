
WITH
existing AS (
	SELECT id, enabled
		FROM pavao.functionality func

		WHERE
			func.package = $1 AND
			func."name" = $2
),

created AS (
	INSERT INTO pavao.functionality (package, name)
		SELECT $1, $2
			WHERE NOT EXISTS (
				SELECT 1
					FROM pavao.functionality fnc

					WHERE
						fnc.package = $1 AND
						fnc."name" = $2
			)

	RETURNING id, enabled
)

SELECT id FROM existing UNION ALL
SELECT id FROM created;
