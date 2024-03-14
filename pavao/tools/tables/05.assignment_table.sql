
CREATE TABLE IF NOT EXISTS pavao.assignment (
  account        INTEGER REFERENCES pavao.account(id) ON DELETE CASCADE,
  "role"         INTEGER REFERENCES pavao."role"(id) ON DELETE CASCADE,
  PRIMARY KEY (account, "role")
);

