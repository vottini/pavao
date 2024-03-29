
CREATE TABLE IF NOT EXISTS pavao.task (
  id             INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  package        TEXT,
  name           TEXT,
  enabled        BOOL,
  managerial     BOOL
);

