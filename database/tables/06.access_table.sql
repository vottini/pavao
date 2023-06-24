
CREATE TABLE pavao.access (
  functionality   INTEGER REFERENCES pavao.functionality(id) ON DELETE CASCADE,
  class           INTEGER REFERENCES pavao.class(id) ON DELETE CASCADE,
  PRIMARY KEY (functionality, class)
);

