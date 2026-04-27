"""Tests for the polling loop in app.py."""

from __future__ import annotations

from unittest.mock import call, patch

import pytest

from steam_library_monitor.app import SteamLibraryMonitor
from steam_library_monitor.config import Config, load_config
from steam_library_monitor.models import AppInfo, NewApp, OwnedGame


def _make_config(appdetails_delay: float = 0.0, sleep_interval: int = 1) -> Config:
    return load_config(
        {
            "STEAM_API_KEY": "key",
            "STEAM_USERS": "76561198000000001=Alice",
            "SMTP_USERNAME": "sender@example.com",
            "SMTP_PASSWORD": "password",
            "SMTP_TO": "to@example.com",
            "SLEEP_INTERVAL": str(sleep_interval),
            "APPDETAILS_DELAY": str(appdetails_delay),
        }
    )


def _make_app_info(app_id: int = 10) -> AppInfo:
    return AppInfo(
        app_id=app_id,
        title="Test Game",
        app_type="game",
        store_url=f"https://store.steampowered.com/app/{app_id}/",
        base_app_id=None,
        base_title=None,
    )


class TestRunForeverSurvivesPollFailure:
    """run_forever must not crash when poll_once raises."""

    def test_continues_loop_after_exception(self) -> None:
        config = _make_config()
        monitor = SteamLibraryMonitor(config)
        poll_count = 0
        sleep_count = 0

        def poll_once_side_effect() -> list[NewApp]:
            nonlocal poll_count
            poll_count += 1
            if poll_count == 1:
                raise RuntimeError("simulated failure")
            return []

        def sleep_side_effect(_seconds: float) -> None:
            nonlocal sleep_count
            sleep_count += 1
            if sleep_count >= 2:
                raise StopIteration("stop the loop")

        with (
            patch.object(monitor, "initialize"),
            patch.object(monitor, "poll_once", side_effect=poll_once_side_effect),
            patch("steam_library_monitor.app.time.sleep", side_effect=sleep_side_effect),
            pytest.raises(StopIteration),
        ):
            monitor.run_forever()

        assert poll_count == 2


class TestAppdetailsDelay:
    """poll_once sleeps before each unknown app's get_app_details call."""

    def test_sleep_called_once_per_unknown_app(self) -> None:
        config = _make_config(appdetails_delay=1.5)
        monitor = SteamLibraryMonitor(config)

        owned_game = OwnedGame(app_id=10, title="Test Game")
        app_info = _make_app_info(10)

        with (
            patch.object(monitor.database, "initialize"),
            patch.object(monitor.database, "start_poll_run", return_value=1),
            patch.object(monitor.database, "finish_poll_run"),
            patch.object(monitor.database, "sync_account_apps", return_value=[]),
            patch.object(monitor.database, "get_app", return_value=None),
            patch.object(monitor.steam_client, "get_owned_games", return_value=[owned_game]),
            patch.object(monitor.steam_client, "get_app_details", return_value=app_info),
            patch("steam_library_monitor.app.time.sleep") as mock_sleep,
        ):
            monitor.poll_once()

        mock_sleep.assert_called_once_with(1.5)

    def test_no_sleep_when_app_cached(self) -> None:
        config = _make_config(appdetails_delay=1.5)
        monitor = SteamLibraryMonitor(config)

        owned_game = OwnedGame(app_id=10, title="Test Game")
        app_info = _make_app_info(10)

        with (
            patch.object(monitor.database, "initialize"),
            patch.object(monitor.database, "start_poll_run", return_value=1),
            patch.object(monitor.database, "finish_poll_run"),
            patch.object(monitor.database, "sync_account_apps", return_value=[]),
            patch.object(monitor.database, "get_app", return_value=app_info),
            patch.object(monitor.steam_client, "get_owned_games", return_value=[owned_game]),
            patch("steam_library_monitor.app.time.sleep") as mock_sleep,
        ):
            monitor.poll_once()

        mock_sleep.assert_not_called()

    def test_sleep_called_for_each_unknown_app(self) -> None:
        config = _make_config(appdetails_delay=2.0)
        monitor = SteamLibraryMonitor(config)

        owned_games = [OwnedGame(app_id=i, title=f"Game {i}") for i in range(3)]

        def fake_get_app_details(app_id: int, _title: str) -> AppInfo:
            return _make_app_info(app_id)

        with (
            patch.object(monitor.database, "initialize"),
            patch.object(monitor.database, "start_poll_run", return_value=1),
            patch.object(monitor.database, "finish_poll_run"),
            patch.object(monitor.database, "sync_account_apps", return_value=[]),
            patch.object(monitor.database, "get_app", return_value=None),
            patch.object(monitor.steam_client, "get_owned_games", return_value=owned_games),
            patch.object(
                monitor.steam_client, "get_app_details", side_effect=fake_get_app_details
            ),
            patch("steam_library_monitor.app.time.sleep") as mock_sleep,
        ):
            monitor.poll_once()

        assert mock_sleep.call_count == 3
        mock_sleep.assert_has_calls([call(2.0), call(2.0), call(2.0)])
