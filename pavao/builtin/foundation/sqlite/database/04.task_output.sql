
CREATE TABLE IF NOT EXISTS task_output (
  id                 INTEGER PRIMARY KEY,
  execution          INTEGER REFERENCES task_execution (id) NOT NULL,
  error              BOOL,
  instant            TIMESTAMP,
  content            TEXT
);

