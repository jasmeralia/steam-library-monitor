"""Tests for the CLI entrypoint."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from steam_library_monitor import __main__ as main_module


def _base_env() -> dict[str, str]:
    return {
        "STEAM_API_KEY": "main-steam-key",
        "STEAM_USERS": "76561198000000009=Riley",
        "SMTP_USERNAME": "sender@main-tests.example.com",
        "SMTP_PASSWORD": "main-app-password",
        "SMTP_TO": "recipient@main-tests.example.com",
    }


class TestRunOnce:
    """--once and RUN_ONCE trigger a single poll_once instead of run_forever."""

    def test_once_flag_runs_single_poll_and_exits(self) -> None:
        mock_monitor = MagicMock()
        with (
            patch.dict("os.environ", _base_env(), clear=True),
            patch.object(main_module, "SteamLibraryMonitor", return_value=mock_monitor),
            patch.object(main_module, "configure_logging"),
        ):
            exit_code = main_module.main(["--once"])

        assert exit_code == 0
        mock_monitor.initialize.assert_called_once()
        mock_monitor.poll_once.assert_called_once()
        mock_monitor.run_forever.assert_not_called()

    def test_run_once_env_var_runs_single_poll(self) -> None:
        env = _base_env()
        env["RUN_ONCE"] = "1"
        mock_monitor = MagicMock()
        with (
            patch.dict("os.environ", env, clear=True),
            patch.object(main_module, "SteamLibraryMonitor", return_value=mock_monitor),
            patch.object(main_module, "configure_logging"),
        ):
            exit_code = main_module.main([])

        assert exit_code == 0
        mock_monitor.initialize.assert_called_once()
        mock_monitor.poll_once.assert_called_once()
        mock_monitor.run_forever.assert_not_called()

    def test_default_runs_forever(self) -> None:
        mock_monitor = MagicMock()
        with (
            patch.dict("os.environ", _base_env(), clear=True),
            patch.object(main_module, "SteamLibraryMonitor", return_value=mock_monitor),
            patch.object(main_module, "configure_logging"),
        ):
            exit_code = main_module.main([])

        assert exit_code == 0
        mock_monitor.run_forever.assert_called_once()
        mock_monitor.initialize.assert_not_called()
        mock_monitor.poll_once.assert_not_called()

    def test_config_error_returns_exit_code_two(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            exit_code = main_module.main([])

        assert exit_code == 2

    def test_poll_failure_in_once_mode_propagates(self) -> None:
        mock_monitor = MagicMock()
        mock_monitor.poll_once.side_effect = RuntimeError("boom")
        with (
            patch.dict("os.environ", _base_env(), clear=True),
            patch.object(main_module, "SteamLibraryMonitor", return_value=mock_monitor),
            patch.object(main_module, "configure_logging"),
            pytest.raises(RuntimeError, match="boom"),
        ):
            main_module.main(["--once"])


class TestEnvFlagSet:
    """_env_flag_set treats common truthy strings as enabled, everything else as disabled."""

    @pytest.mark.parametrize("value", ["1", "true", "True", "yes", "on", " 1 "])
    def test_truthy_values(self, value: str) -> None:
        # pylint: disable-next=protected-access
        assert main_module._env_flag_set(value) is True

    @pytest.mark.parametrize("value", [None, "", "0", "false", "no", "off"])
    def test_falsy_values(self, value: str | None) -> None:
        # pylint: disable-next=protected-access
        assert main_module._env_flag_set(value) is False
