CREATE TABLE daily_metrics (
  day TEXT NOT NULL,
  event TEXT NOT NULL,
  path TEXT NOT NULL,
  source TEXT NOT NULL,
  total INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY(day, event, path, source)
) WITHOUT ROWID;
