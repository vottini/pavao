
CREATE TABLE pavao.authentication (
  id              INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  account         INTEGER REFERENCES pavao.account(id),
  hash            TEXT,
  active          BOOLEAN DEFAULT TRUE,
  needs_change    BOOLEAN DEFAULT TRUE,
  last_login      TIMESTAMP WITH TIME ZONE 
);

