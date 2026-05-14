from __future__ import annotations

import sqlite3
from pathlib import Path

from steam_library_monitor.db import Database
from steam_library_monitor.models import AppInfo, SteamUser


def app(app_id: int, title: str = "Example Game") -> AppInfo:
    return AppInfo(
        app_id=app_id,
        title=title,
        app_type="game",
        store_url=f"https://store.steampowered.com/app/{app_id}/",
    )


def test_creates_schema_on_empty_db(tmp_path: Path) -> None:
    db_path = tmp_path / "library-cache.db"
    database = Database(str(db_path))

    database.initialize()

    with sqlite3.connect(db_path) as connection:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
    assert {"accounts", "apps", "account_apps", "poll_runs"}.issubset(tables)


def test_migration_adds_release_year_to_existing_db(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy.db"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE apps (
                app_id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                app_type TEXT,
                store_url TEXT NOT NULL,
                base_app_id INTEGER,
                base_title TEXT,
                raw_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

    database = Database(str(db_path))
    database.initialize()

    with sqlite3.connect(db_path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(apps)")}
    assert "release_year" in columns


def test_first_sync_inserts_baseline_without_notification(tmp_path: Path) -> None:
    database = Database(str(tmp_path / "cache.db"))
    database.initialize()
    user = SteamUser("76561198000000001", "Alice")

    new_items = database.sync_account_apps(user, [app(10)])

    assert new_items == []


def test_get_app_returns_stored_app_info(tmp_path: Path) -> None:
    database = Database(str(tmp_path / "cache.db"))
    database.initialize()
    user = SteamUser("76561198000000001", "Alice")
    app_info = AppInfo(
        app_id=10,
        title="Example DLC",
        app_type="dlc",
        store_url="https://store.steampowered.com/app/10/",
        base_app_id=20,
        base_title="Example Game",
        raw_json='{"type": "dlc"}',
    )

    assert database.get_app(10) is None

    database.sync_account_apps(user, [app_info])

    assert database.get_app(10) == app_info


def test_second_sync_with_no_changes_emits_no_new_items(tmp_path: Path) -> None:
    database = Database(str(tmp_path / "cache.db"))
    database.initialize()
    user = SteamUser("76561198000000001", "Alice")
    database.sync_account_apps(user, [app(10)])

    new_items = database.sync_account_apps(user, [app(10)])

    assert new_items == []


def test_second_sync_with_new_app_emits_new_item(tmp_path: Path) -> None:
    database = Database(str(tmp_path / "cache.db"))
    database.initialize()
    user = SteamUser("76561198000000001", "Alice")
    database.sync_account_apps(user, [app(10)])

    new_items = database.sync_account_apps(user, [app(10), app(11, "New Game")])

    assert len(new_items) == 1
    assert new_items[0].app.app_id == 11


def test_cache_app_persists_without_account_link(tmp_path: Path) -> None:
    database = Database(str(tmp_path / "cache.db"))
    database.initialize()
    ignored_app = AppInfo(
        app_id=99,
        title="Promo Ad",
        app_type="advertising",
        store_url="https://store.steampowered.com/app/99/",
    )

    database.cache_app(ignored_app)

    assert database.get_app(99) == ignored_app


def test_tracks_per_account_app_additions_separately(tmp_path: Path) -> None:
    database = Database(str(tmp_path / "cache.db"))
    database.initialize()
    alice = SteamUser("76561198000000001", "Alice")
    bob = SteamUser("76561198000000002", "Bob")
    database.sync_account_apps(alice, [app(10)])
    database.sync_account_apps(bob, [app(10)])

    alice_new = database.sync_account_apps(alice, [app(10), app(11)])
    bob_new = database.sync_account_apps(bob, [app(10)])

    assert [item.app.app_id for item in alice_new] == [11]
    assert bob_new == []
