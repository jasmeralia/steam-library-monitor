"""Shared data models for steam-library-monitor."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SteamUser:
    """Configured Steam account."""

    steam_id: str
    display_name: str


@dataclass(frozen=True)
class OwnedGame:
    """Game entry returned by Steam's owned games API."""

    app_id: int
    title: str


@dataclass(frozen=True)
class AppInfo:
    """Stored Steam app metadata."""

    app_id: int
    title: str
    app_type: str | None
    store_url: str
    base_app_id: int | None = None
    base_title: str | None = None
    raw_json: str | None = None


@dataclass(frozen=True)
class NewApp:
    """Newly observed app for an account."""

    steam_id: str
    display_name: str
    app: AppInfo
