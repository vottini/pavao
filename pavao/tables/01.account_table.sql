
CREATE TABLE IF NOT EXISTS pavao.account (
  id              INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  login           TEXT NOT NULL UNIQUE,
  first_name      TEXT NOT NULL,
  last_name       TEXT,
  active          BOOLEAN DEFAULT TRUE,
  creation        TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  last_login      TIMESTAMP WITH TIME ZONE,
  managerial      BOOL DEFAULT FALSE
);


