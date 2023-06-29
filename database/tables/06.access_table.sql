
CREATE TABLE pavao.access (
  functionality   INTEGER REFERENCES pavao.functionality(id) ON DELETE CASCADE,
  cls             INTEGER REFERENCES pavao.class(id) ON DELETE CASCADE,
  PRIMARY KEY (functionality, cls)
);

