
CREATE TABLE IF NOT EXISTS pavao."role" (
  id              INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  name            TEXT NOT NULL UNIQUE,
  description     TEXT,
  admin           BOOL DEFAULT FALSE
);

