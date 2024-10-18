
CREATE TABLE IF NOT EXISTS task_execution (
  id                 INTEGER PRIMARY KEY,
  task               INTEGER REFERENCES task (id) NOT NULL,
  execution_start    TIMESTAMP,
  execution_end      TIMESTAMP,
  success            BOOL
);

