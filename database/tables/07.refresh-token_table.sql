
CREATE TABLE pavao.refresh_token (
  account     INTEGER REFERENCES pavao.account(id) ON DELETE CASCADE,
  hashed_jti  TEXT,
  expiry      TIMESTAMP WITH TIME ZONE,
  PRIMARY KEY (account, hashed_jti)
);

