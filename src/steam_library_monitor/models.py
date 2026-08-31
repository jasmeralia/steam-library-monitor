"""Shared data models for steam-library-monitor."""

from __future__ import annotations

from dataclasses import dataclass

# Legacy fallback only: recently added apps' assets live under a hashed
# store_item_assets path and 404 here, so prefer header_image_url when set.
_COVER_URL = "https://cdn.akamai.steamstatic.com/steam/apps/{app_id}/header.jpg"


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
    release_year: int | None = None
    header_image_url: str | None = None

    @property
    def cover_url(self) -> str:
        return self.header_image_url or _COVER_URL.format(app_id=self.app_id)


@dataclass(frozen=True)
class NewApp:
    """Newly observed app for an account."""

    steam_id: str
    display_name: str
    app: AppInfo
