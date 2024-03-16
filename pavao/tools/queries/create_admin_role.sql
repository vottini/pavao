
WITH

existing (id) AS (
	SELECT id FROM pavao."role"
	WHERE "name" = $1
),

created (id) AS (
	INSERT INTO
		pavao."role" (name, admin)
		SELECT $1, TRUE
			WHERE NOT EXISTS (
				SELECT id FROM pavao."role"
		  		WHERE "name" = $1
			)

	RETURNING id
)

SELECT id FROM existing UNION ALL
SELECT id from created;

