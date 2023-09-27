
CREATE TABLE pavao.functionality (
  id              INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  name            TEXT NOT NULL UNIQUE,
  enabled         BOOL DEFAULT TRUE,
  category        TEXT
);

