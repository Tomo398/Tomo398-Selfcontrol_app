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

-- C: 日付を持たない繰り返し予定（生活ルーティン）
CREATE TABLE IF NOT EXISTS routine_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  mode TEXT NOT NULL CHECK(mode IN ('fixed_time', 'duration_only')),
  start_time TEXT,              -- HH:MM, fixed_time用
  end_time TEXT,                -- HH:MM, fixed_time用
  duration_minutes INTEGER,     -- duration_only用
  weekdays TEXT NOT NULL DEFAULT '0,1,2,3,4,5,6',
  remind_start INTEGER NOT NULL DEFAULT 0,
  remind_end INTEGER NOT NULL DEFAULT 0,
  note TEXT NOT NULL DEFAULT '',
  CHECK (
    (
      mode = 'fixed_time'
      AND start_time IS NOT NULL
      AND end_time IS NOT NULL
      AND start_time < end_time
    )
    OR
    (
      mode = 'duration_only'
      AND duration_minutes IS NOT NULL
      AND duration_minutes > 0
    )
  )
);

-- A: 締切と必要工数を持つタスク
CREATE TABLE IF NOT EXISTS a_tasks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  start_date TEXT NOT NULL, -- YYYY-MM-DD
  deadline_date TEXT NOT NULL, -- YYYY-MM-DD
  total_minutes INTEGER NOT NULL CHECK(total_minutes >= 0),
  remaining_minutes INTEGER NOT NULL CHECK(remaining_minutes >= 0),
  status TEXT NOT NULL DEFAULT 'active'
    CHECK(status IN ('active', 'completed', 'incomplete')),
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Aタスク候補メモ（正式なAタスク化前の控え）
CREATE TABLE IF NOT EXISTS a_task_candidates (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  memo TEXT NOT NULL DEFAULT '',
  category TEXT NOT NULL DEFAULT '',
  is_converted INTEGER NOT NULL DEFAULT 0 CHECK(is_converted IN (0, 1)),
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

-- アプリ内設定
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

-- 便利なインデックス（最低限）
CREATE INDEX IF NOT EXISTS idx_events_start ON events(start_dt);
CREATE INDEX IF NOT EXISTS idx_events_type  ON events(type);
CREATE INDEX IF NOT EXISTS idx_routine_events_mode ON routine_events(mode);
CREATE INDEX IF NOT EXISTS idx_tasks_deadline ON a_tasks(deadline_date);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON a_tasks(status);
CREATE INDEX IF NOT EXISTS idx_task_candidates_converted ON a_task_candidates(is_converted, created_at);
CREATE INDEX IF NOT EXISTS idx_logs_date ON daily_logs(log_date);
