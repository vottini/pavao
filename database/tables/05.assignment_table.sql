
CREATE TABLE pavao.assignment (
  account         INTEGER REFERENCES pavao.account(id) ON DELETE CASCADE,
  class           INTEGER REFERENCES pavao.class(id) ON DELETE CASCADE,
  PRIMARY KEY (account, class)
);

