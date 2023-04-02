
CREATE TABLE pavao.access (
  functionality   INTEGER REFERENCES pavao.functionality(id) ON DELETE CASCADE,
  account         INTEGER REFERENCES pavao.account(id) ON DELETE CASCADE,
  class           INTEGER REFERENCES pavao.class(id) ON DELETE CASCADE,
  PRIMARY KEY (functionality, account, class)
);

