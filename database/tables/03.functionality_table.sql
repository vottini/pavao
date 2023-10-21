
CREATE TABLE pavao.functionality (
  id              INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  package         TEXT,
  name            TEXT NOT NULL,
  enabled         BOOL DEFAULT TRUE,
  in_use          BOOL DEFAULT TRUE,
  UNIQUE (package, name)
);

