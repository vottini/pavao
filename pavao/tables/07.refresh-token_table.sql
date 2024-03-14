
CREATE TABLE IF NOT EXISTS pavao.refresh_token (
  id                  INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  account             INTEGER REFERENCES pavao.account(id) ON DELETE CASCADE,
  hashed_jti          TEXT,
  expiration          TIMESTAMP WITH TIME ZONE,
  access_token        TEXT
);

