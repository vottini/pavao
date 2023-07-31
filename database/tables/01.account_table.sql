
CREATE TABLE pavao.account (
  id              INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  login           TEXT NOT NULL UNIQUE,
  first_name      TEXT NOT NULL,
  last_name       TEXT,
  creation        TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  managerial      BOOL DEFAULT FALSE
);


