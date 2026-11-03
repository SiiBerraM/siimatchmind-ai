"""قاعدة البيانات (SQLite من المكتبة القياسية): الفرق والمباريات والإحصائيات والمستخدمون والتوقعات.

المسار الافتراضي: backend/data/smm.db ويمكن تغييره بمتغير البيئة SMM_DB.
"""
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS leagues (code TEXT PRIMARY KEY, name TEXT NOT NULL, source TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS teams (id TEXT PRIMARY KEY, name TEXT NOT NULL, source TEXT NOT NULL, logo TEXT);
CREATE TABLE IF NOT EXISTS matches (
  id TEXT PRIMARY KEY, date TEXT NOT NULL, time TEXT, round INTEGER, season TEXT, league TEXT,
  home TEXT NOT NULL, away TEXT NOT NULL, hg INTEGER, ag INTEGER, status TEXT NOT NULL, source TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(date);
CREATE TABLE IF NOT EXISTS match_stats (
  match_id TEXT NOT NULL, team_id TEXT NOT NULL, possession REAL, shots INTEGER, shots_on INTEGER, corners INTEGER,
  PRIMARY KEY (match_id, team_id));
CREATE TABLE IF NOT EXISTS stats_tried (match_id TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS availability (match_id TEXT PRIMARY KEY, payload TEXT NOT NULL, fetched TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT NOT NULL UNIQUE, pw_hash TEXT NOT NULL, created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL, expires TEXT NOT NULL,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS login_attempts (email TEXT NOT NULL, at TEXT NOT NULL, ok INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS favorites (
  user_id INTEGER NOT NULL, home TEXT NOT NULL, away TEXT NOT NULL, created TEXT NOT NULL,
  PRIMARY KEY (user_id, home, away), FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS fav_teams (
  user_id INTEGER NOT NULL, team_id TEXT NOT NULL, created TEXT NOT NULL,
  PRIMARY KEY (user_id, team_id), FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS history (
  user_id INTEGER NOT NULL, home TEXT NOT NULL, away TEXT NOT NULL, p_home INTEGER, p_draw INTEGER, p_away INTEGER,
  at TEXT NOT NULL, PRIMARY KEY (user_id, home, away), FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS predictions (
  id INTEGER PRIMARY KEY AUTOINCREMENT, match_id TEXT NOT NULL, day TEXT NOT NULL, home TEXT NOT NULL, away TEXT NOT NULL,
  p_home REAL NOT NULL, p_draw REAL NOT NULL, p_away REAL NOT NULL, logged_at TEXT NOT NULL,
  UNIQUE (match_id, day));
"""


def path():
    return os.environ.get("SMM_DB") or str(Path(__file__).resolve().parent / "data" / "smm.db")


@contextmanager
def connect():
    p = path()
    if p != ":memory:":
        Path(p).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(p)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA)
    if "logo" not in [r["name"] for r in con.execute("PRAGMA table_info(teams)")]:      # ترحيل قاعدة أُنشئت قبل إضافة الشعارات
        con.execute("ALTER TABLE teams ADD COLUMN logo TEXT")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def kv_get(con, k, default=None):
    r = con.execute("SELECT v FROM kv WHERE k=?", (k,)).fetchone()
    return r["v"] if r else default


def kv_set(con, k, v):
    con.execute("INSERT INTO kv(k, v) VALUES(?, ?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, str(v)))
