
CREATE TABLE IF NOT EXISTS pavao.authentication (
  id              INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  account         INTEGER REFERENCES pavao.account(id),
  hash            TEXT,
  needs_change    BOOLEAN DEFAULT TRUE
);

