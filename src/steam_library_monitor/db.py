"""SQLite persistence layer."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from steam_library_monitor.models import AppInfo, NewApp, SteamUser

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    steam_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS apps (
    app_id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    app_type TEXT,
    store_url TEXT NOT NULL,
    base_app_id INTEGER,
    base_title TEXT,
    raw_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS account_apps (
    steam_id TEXT NOT NULL,
    app_id INTEGER NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    PRIMARY KEY (steam_id, app_id),
    FOREIGN KEY (steam_id) REFERENCES accounts(steam_id),
    FOREIGN KEY (app_id) REFERENCES apps(app_id)
);

CREATE TABLE IF NOT EXISTS poll_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    message TEXT
);
"""


class Database:
    """Small SQLite wrapper for monitor state."""

    def __init__(self, path: str) -> None:
        self.path = path

    def connect(self) -> sqlite3.Connection:
        """Open a configured SQLite connection."""

        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        """Create database schema if needed."""

        with self.connect() as connection:
            connection.executescript(SCHEMA)

    def start_poll_run(self) -> int:
        """Record a poll run start and return its row id."""

        now = utc_now()
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO poll_runs (started_at, status) VALUES (?, ?)",
                (now, "running"),
            )
            if cursor.lastrowid is None:
                raise RuntimeError("SQLite did not return a poll_runs row id")
            return int(cursor.lastrowid)

    def finish_poll_run(self, run_id: int, status: str, message: str | None = None) -> None:
        """Mark a poll run complete."""

        with self.connect() as connection:
            connection.execute(
                """
                UPDATE poll_runs
                SET finished_at = ?, status = ?, message = ?
                WHERE id = ?
                """,
                (utc_now(), status, message, run_id),
            )

    def cache_app(self, app: AppInfo) -> None:
        """Persist app metadata without linking it to any account."""

        now = utc_now()
        with self.connect() as connection:
            _upsert_app(connection, app, now)

    def get_app(self, app_id: int) -> AppInfo | None:
        """Return stored app metadata for app_id, if present."""

        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT app_id, title, app_type, store_url, base_app_id,
                    base_title, raw_json
                FROM apps
                WHERE app_id = ?
                """,
                (app_id,),
            ).fetchone()
        if row is None:
            return None
        return AppInfo(
            app_id=row["app_id"],
            title=row["title"],
            app_type=row["app_type"],
            store_url=row["store_url"],
            base_app_id=row["base_app_id"],
            base_title=row["base_title"],
            raw_json=row["raw_json"],
        )

    def sync_account_apps(
        self,
        user: SteamUser,
        apps: Iterable[AppInfo],
    ) -> list[NewApp]:
        """Persist a user's current apps and return newly observed rows.

        The first sync for an account establishes the baseline and returns no
        notifications.
        """

        app_list = list(apps)
        now = utc_now()
        with self.connect() as connection:
            existed = _account_exists(connection, user.steam_id)
            _upsert_account(connection, user, now)
            new_items: list[NewApp] = []
            for app in app_list:
                _upsert_app(connection, app, now)
                account_app_exists = connection.execute(
                    """
                    SELECT 1 FROM account_apps
                    WHERE steam_id = ? AND app_id = ?
                    """,
                    (user.steam_id, app.app_id),
                ).fetchone()
                if account_app_exists:
                    connection.execute(
                        """
                        UPDATE account_apps
                        SET last_seen_at = ?
                        WHERE steam_id = ? AND app_id = ?
                        """,
                        (now, user.steam_id, app.app_id),
                    )
                else:
                    connection.execute(
                        """
                        INSERT INTO account_apps
                            (steam_id, app_id, first_seen_at, last_seen_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        (user.steam_id, app.app_id, now, now),
                    )
                    if existed:
                        new_items.append(
                            NewApp(
                                steam_id=user.steam_id,
                                display_name=user.display_name,
                                app=app,
                            )
                        )
            return new_items


def utc_now() -> str:
    """Return current UTC time in ISO-8601 form."""

    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _account_exists(connection: sqlite3.Connection, steam_id: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM accounts WHERE steam_id = ?",
            (steam_id,),
        ).fetchone()
        is not None
    )


def _upsert_account(connection: sqlite3.Connection, user: SteamUser, now: str) -> None:
    connection.execute(
        """
        INSERT INTO accounts (steam_id, display_name, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(steam_id) DO UPDATE SET
            display_name = excluded.display_name,
            updated_at = excluded.updated_at
        """,
        (user.steam_id, user.display_name, now, now),
    )


def _upsert_app(connection: sqlite3.Connection, app: AppInfo, now: str) -> None:
    raw_json = app.raw_json
    if raw_json is not None:
        json.loads(raw_json)
    connection.execute(
        """
        INSERT INTO apps (
            app_id, title, app_type, store_url, base_app_id, base_title,
            raw_json, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(app_id) DO UPDATE SET
            title = excluded.title,
            app_type = excluded.app_type,
            store_url = excluded.store_url,
            base_app_id = excluded.base_app_id,
            base_title = excluded.base_title,
            raw_json = excluded.raw_json,
            updated_at = excluded.updated_at
        """,
        (
            app.app_id,
            app.title,
            app.app_type,
            app.store_url,
            app.base_app_id,
            app.base_title,
            raw_json,
            now,
            now,
        ),
    )
