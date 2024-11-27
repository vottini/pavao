
INSERT INTO
  settings (name, type, value)
  VALUES ($1, $2, $3)

  ON CONFLICT (name) DO UPDATE
    SET type = excluded.type,
        value = excluded.value;

