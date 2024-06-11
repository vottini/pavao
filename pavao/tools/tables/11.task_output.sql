
CREATE TABLE IF NOT EXISTS pavao.task_output (
  id                 INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  task               INTEGER REFERENCES pavao.task (id) NOT NULL,
  instant            TIMESTAMP WITH TIME ZONE,
  content            TEXT
);

