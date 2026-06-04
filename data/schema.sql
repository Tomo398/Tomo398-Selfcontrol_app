PRAGMA foreign_keys = ON;

-- B/C: 時間枠の予定（突発予定・習慣）
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  type TEXT NOT NULL CHECK(type IN ('B','C')),
  title TEXT NOT NULL,
  start_dt TEXT NOT NULL,   -- ISO8601: YYYY-MM-DDTHH:MM:SS
  end_dt   TEXT NOT NULL,   -- ISO8601
  remind_start INTEGER NOT NULL DEFAULT 0,
  remind_end   INTEGER NOT NULL DEFAULT 0,
  note TEXT NOT NULL DEFAULT ''
);

-- A: 締切と必要工数を持つタスク
CREATE TABLE IF NOT EXISTS a_tasks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  deadline_date TEXT NOT NULL, -- YYYY-MM-DD
  total_minutes INTEGER NOT NULL CHECK(total_minutes >= 0),
  remaining_minutes INTEGER NOT NULL CHECK(remaining_minutes >= 0),
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 日次ログ（実績と反省）
CREATE TABLE IF NOT EXISTS daily_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  log_date TEXT NOT NULL,       -- YYYY-MM-DD
  a_task_id INTEGER NOT NULL,
  actual_minutes INTEGER NOT NULL DEFAULT 0 CHECK(actual_minutes >= 0),
  reflection TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (a_task_id) REFERENCES a_tasks(id) ON DELETE CASCADE,
  UNIQUE (log_date, a_task_id)
);

-- 便利なインデックス（最低限）
CREATE INDEX IF NOT EXISTS idx_events_start ON events(start_dt);
CREATE INDEX IF NOT EXISTS idx_events_type  ON events(type);
CREATE INDEX IF NOT EXISTS idx_tasks_deadline ON a_tasks(deadline_date);
CREATE INDEX IF NOT EXISTS idx_logs_date ON daily_logs(log_date);
