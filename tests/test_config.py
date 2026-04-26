from __future__ import annotations

import pytest

from steam_library_monitor.config import ConfigError, load_config


def base_env() -> dict[str, str]:
    return {
        "STEAM_API_KEY": "steam-key",
        "STEAM_USERS": "76561198000000001=Alice",
        "SMTP_USERNAME": "sender@gmail.com",
        "SMTP_PASSWORD": "app-password",
        "SMTP_TO": "recipient@example.com",
    }


def test_valid_steam_users_with_one_user() -> None:
    config = load_config(base_env())

    assert config.steam_users[0].steam_id == "76561198000000001"
    assert config.steam_users[0].display_name == "Alice"


def test_valid_steam_users_with_multiple_users() -> None:
    env = base_env()
    env["STEAM_USERS"] = "76561198000000001=Alice,76561198000000002=Bob"

    config = load_config(env)

    assert [user.display_name for user in config.steam_users] == ["Alice", "Bob"]


def test_missing_steam_api_key_is_invalid() -> None:
    env = base_env()
    env.pop("STEAM_API_KEY")

    with pytest.raises(ConfigError, match="STEAM_API_KEY"):
        load_config(env)


def test_malformed_steam_users_is_invalid() -> None:
    env = base_env()
    env["STEAM_USERS"] = "not-an-assignment"

    with pytest.raises(ConfigError, match="STEAM_USERS"):
        load_config(env)


def test_defaults() -> None:
    config = load_config(base_env())

    assert config.sleep_interval == 86_400
    assert config.log_level == "WARNING"
