
CREATE TABLE IF NOT EXISTS task (
  id             INTEGER PRIMARY KEY,
  package        TEXT,
  name           TEXT NOT NULL,
  enabled        BOOL DEFAULT(TRUE)
);

