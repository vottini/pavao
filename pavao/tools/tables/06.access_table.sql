
CREATE TABLE IF NOT EXISTS pavao.access (
  functionality   INTEGER REFERENCES pavao.functionality(id) ON DELETE CASCADE,
  "role"          INTEGER REFERENCES pavao."role"(id) ON DELETE CASCADE,
  PRIMARY KEY (functionality, "role")
);

