import Database from 'better-sqlite3';
import { mkdirSync } from 'fs';
import { dirname } from 'path';

export function initDb(dbPath) {
  mkdirSync(dirname(dbPath), { recursive: true });

  const db = new Database(dbPath);

  db.pragma('journal_mode = WAL');
  db.pragma('foreign_keys = ON');

  db.exec(`
    CREATE TABLE IF NOT EXISTS contests (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      description TEXT,
      start_time TEXT NOT NULL,
      end_time TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'active', 'completed')),
      rules TEXT,
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS clubs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      callsign TEXT NOT NULL,
      contest_id INTEGER NOT NULL REFERENCES contests(id) ON DELETE CASCADE,
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS operators (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      callsign TEXT NOT NULL,
      club_id INTEGER NOT NULL REFERENCES clubs(id) ON DELETE CASCADE,
      contest_id INTEGER NOT NULL REFERENCES contests(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS qsos (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      contest_id INTEGER NOT NULL REFERENCES contests(id) ON DELETE CASCADE,
      station_callsign TEXT NOT NULL,
      call TEXT NOT NULL,
      band TEXT,
      mode TEXT,
      frequency REAL,
      rst_sent TEXT,
      rst_rcvd TEXT,
      gridsquare TEXT,
      my_gridsquare TEXT,
      qso_date TEXT,
      time_on TEXT,
      time_off TEXT,
      is_multiplier INTEGER NOT NULL DEFAULT 0,
      points INTEGER NOT NULL DEFAULT 1,
      raw_adif TEXT,
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE INDEX IF NOT EXISTS idx_clubs_contest ON clubs(contest_id);
    CREATE INDEX IF NOT EXISTS idx_operators_club ON operators(club_id);
    CREATE INDEX IF NOT EXISTS idx_operators_contest ON operators(contest_id);
    CREATE INDEX IF NOT EXISTS idx_qsos_contest ON qsos(contest_id);
    CREATE INDEX IF NOT EXISTS idx_qsos_station ON qsos(station_callsign);
    CREATE INDEX IF NOT EXISTS idx_qsos_band ON qsos(band);
    CREATE INDEX IF NOT EXISTS idx_qsos_mode ON qsos(mode);
    CREATE INDEX IF NOT EXISTS idx_qsos_date_time ON qsos(qso_date, time_on);
    CREATE INDEX IF NOT EXISTS idx_qsos_gridsquare ON qsos(gridsquare);
    CREATE INDEX IF NOT EXISTS idx_qsos_contest_station ON qsos(contest_id, station_callsign);
  `);

  return db;
}
