
INSERT INTO
  settings (name, type, value)
  VALUES (:name, :type, :value)

  ON CONFLICT (name) DO UPDATE
    SET type = excluded.type,
        value = excluded.value;

