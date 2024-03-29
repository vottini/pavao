
CREATE TABLE IF NOT EXISTS pavao.task_execution (
  id                 INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  task               INTEGER REFERENCES pavao.task (id) NOT NULL,
  success            BOOL,
  result             TEXT,
  execution_start    TIMESTAMP WITH TIME ZONE,
  execution_end      TIMESTAMP WITH TIME ZONE
);

