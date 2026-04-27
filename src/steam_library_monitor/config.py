"""Environment configuration parsing."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

from steam_library_monitor.models import SteamUser

DEFAULT_SLEEP_INTERVAL = 86_400
DEFAULT_LOG_LEVEL = "WARNING"
DEFAULT_DATABASE_PATH = "/data/library-cache.db"
DEFAULT_SMTP_HOST = "smtp.gmail.com"
DEFAULT_SMTP_PORT = 587
DEFAULT_APPDETAILS_DELAY = 1.5


@dataclass(frozen=True)
class Config:
    """Runtime configuration."""

    steam_api_key: str
    steam_users: tuple[SteamUser, ...]
    smtp_username: str
    smtp_password: str
    smtp_to: str
    sleep_interval: int = DEFAULT_SLEEP_INTERVAL
    log_level: str = DEFAULT_LOG_LEVEL
    database_path: str = DEFAULT_DATABASE_PATH
    smtp_from: str | None = None
    smtp_host: str = DEFAULT_SMTP_HOST
    smtp_port: int = DEFAULT_SMTP_PORT
    appdetails_delay: float = DEFAULT_APPDETAILS_DELAY

    @property
    def sender(self) -> str:
        """Return configured sender address/header."""

        return self.smtp_from or self.smtp_username


class ConfigError(ValueError):
    """Raised when environment configuration is invalid."""


def load_config(env: Mapping[str, str] | None = None) -> Config:
    """Load configuration from an environment mapping."""

    source = os.environ if env is None else env
    steam_api_key = _required(source, "STEAM_API_KEY")
    steam_users = _parse_steam_users(_required(source, "STEAM_USERS"))
    smtp_username = _required(source, "SMTP_USERNAME")
    smtp_password = _required(source, "SMTP_PASSWORD")
    smtp_to = _required(source, "SMTP_TO")

    sleep_interval = _parse_int(
        source.get("SLEEP_INTERVAL", str(DEFAULT_SLEEP_INTERVAL)),
        "SLEEP_INTERVAL",
        minimum=1,
    )
    smtp_port = _parse_int(
        source.get("SMTP_PORT", str(DEFAULT_SMTP_PORT)),
        "SMTP_PORT",
        minimum=1,
    )
    log_level = source.get("LOG_LEVEL", DEFAULT_LOG_LEVEL).upper()
    valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    if log_level not in valid_levels:
        raise ConfigError(f"LOG_LEVEL must be one of {', '.join(sorted(valid_levels))}")
    appdetails_delay = _parse_float(
        source.get("APPDETAILS_DELAY", str(DEFAULT_APPDETAILS_DELAY)),
        "APPDETAILS_DELAY",
        minimum=0.0,
    )

    return Config(
        steam_api_key=steam_api_key,
        steam_users=steam_users,
        smtp_username=smtp_username,
        smtp_password=smtp_password,
        smtp_to=smtp_to,
        sleep_interval=sleep_interval,
        log_level=log_level,
        database_path=source.get("DATABASE_PATH", DEFAULT_DATABASE_PATH),
        smtp_from=source.get("SMTP_FROM") or None,
        smtp_host=source.get("SMTP_HOST", DEFAULT_SMTP_HOST),
        smtp_port=smtp_port,
        appdetails_delay=appdetails_delay,
    )


def _required(env: Mapping[str, str], name: str) -> str:
    value = env.get(name, "").strip()
    if not value:
        raise ConfigError(f"{name} is required")
    return value


def _parse_float(value: str, name: str, minimum: float) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number") from exc
    if parsed < minimum:
        raise ConfigError(f"{name} must be >= {minimum}")
    return parsed


def _parse_int(value: str, name: str, minimum: int) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer") from exc
    if parsed < minimum:
        raise ConfigError(f"{name} must be >= {minimum}")
    return parsed


def _parse_steam_users(value: str) -> tuple[SteamUser, ...]:
    users: list[SteamUser] = []
    for raw_part in value.split(","):
        part = raw_part.strip()
        if not part:
            continue
        if "=" not in part:
            raise ConfigError("STEAM_USERS entries must use STEAMID64=Display Name")
        steam_id, display_name = (segment.strip() for segment in part.split("=", 1))
        if not steam_id or not display_name:
            raise ConfigError("STEAM_USERS entries require SteamID64 and display name")
        if not steam_id.isdigit():
            raise ConfigError("STEAM_USERS SteamID64 values must be numeric")
        users.append(SteamUser(steam_id=steam_id, display_name=display_name))
    if not users:
        raise ConfigError("STEAM_USERS must include at least one user")
    return tuple(users)
