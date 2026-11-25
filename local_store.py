"""Private, on-device practice history for the browser-based local app."""
from __future__ import annotations

import os
import sqlite3
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

DATA_DIR = Path(os.environ.get("LEETCODE_COACH_DATA_DIR", Path(__file__).parent / ".local_data"))
API_KEY_FILE = DATA_DIR / "claude_api_key"


def load_api_key() -> str:
    """Read the user's local secret, never from the practice database."""
    if not API_KEY_FILE.exists():
        return ""
    if API_KEY_FILE.is_symlink():
        raise OSError("The saved API key path is a symlink; refusing to read it.")
    return API_KEY_FILE.read_text(encoding="utf-8").strip()


def save_api_key(key: str) -> None:
    key = key.strip()
    if not key:
        raise ValueError("Paste an API key before saving it.")
    DATA_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    if API_KEY_FILE.is_symlink():
        raise OSError("The saved API key path is a symlink; refusing to overwrite it.")
    descriptor, temp_path = tempfile.mkstemp(prefix=".claude_key_", dir=DATA_DIR)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            output.write(key)
        os.chmod(temp_path, 0o600)
        os.replace(temp_path, API_KEY_FILE)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def delete_api_key() -> None:
    if API_KEY_FILE.is_symlink():
        raise OSError("The saved API key path is a symlink; refusing to delete it.")
    API_KEY_FILE.unlink(missing_ok=True)


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DATA_DIR / "practice.sqlite3")
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE IF NOT EXISTS attempts (
        id INTEGER PRIMARY KEY, problem_title TEXT NOT NULL, topic TEXT NOT NULL,
        difficulty TEXT NOT NULL, practice_date TEXT NOT NULL,
        outcome TEXT NOT NULL, minutes INTEGER, notes TEXT NOT NULL DEFAULT '',
        review_on TEXT, source_uid TEXT UNIQUE,
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS settings (
        name TEXT PRIMARY KEY, value TEXT NOT NULL
    )""")
    db.commit()
    try:
        with db:
            yield db
    finally:
        db.close()


def attempts() -> list[dict]:
    with connect() as db:
        return [dict(row) for row in db.execute(
            "SELECT * FROM attempts ORDER BY practice_date DESC, id DESC"
        )]


def save(row: dict) -> None:
    with connect() as db:
        db.execute("""INSERT OR IGNORE INTO attempts
            (problem_title, topic, difficulty, practice_date, outcome, minutes,
             notes, review_on, source_uid) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            tuple(row.get(k) for k in (
                "problem_title", "topic", "difficulty", "practice_date",
                "outcome", "minutes", "notes", "review_on", "source_uid")),
        )


def get_setting(name: str) -> str:
    with connect() as db:
        row = db.execute("SELECT value FROM settings WHERE name=?", (name,)).fetchone()
        return row["value"] if row else ""


def set_setting(name: str, value: str) -> None:
    with connect() as db:
        db.execute("INSERT INTO settings VALUES (?, ?) ON CONFLICT(name) DO UPDATE SET value=excluded.value", (name, value))


def import_legacy(rows: list[dict]) -> int:
    """Import legacy rows idempotently, without a cloud user ID."""
    with connect() as db:
        before = db.total_changes
        for row in rows:
            db.execute("""INSERT OR IGNORE INTO attempts
                (problem_title, topic, difficulty, practice_date, outcome, minutes,
                 notes, review_on, source_uid) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                tuple(row.get(k) for k in (
                    "problem_title", "topic", "difficulty", "practice_date",
                    "outcome", "minutes", "notes", "review_on", "source_uid")),
            )
        return db.total_changes - before
