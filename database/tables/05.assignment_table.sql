
CREATE TABLE pavao.assignment (
  account        INTEGER REFERENCES pavao.account(id) ON DELETE CASCADE,
  cls            INTEGER REFERENCES pavao.class(id) ON DELETE CASCADE,
  PRIMARY KEY (account, cls)
);

