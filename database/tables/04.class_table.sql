
CREATE TABLE pavao.class (
  id              INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  name            TEXT NOT NULL UNIQUE,
  description     TEXT
);

