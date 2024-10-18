
CREATE TABLE IF NOT EXISTS task_output (
  id                 INTEGER PRIMARY KEY,
  task               INTEGER REFERENCES task (id) NOT NULL,
  instant            TIMESTAMP,
  content            TEXT
);

