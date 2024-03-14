
CREATE TABLE IF NOT EXISTS pavao.functionality (
  id              INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  package         TEXT,
  name            TEXT NOT NULL,
  enabled         BOOL DEFAULT TRUE,
  active          BOOL DEFAULT TRUE,
  UNIQUE (package, name)
);

