"""Steam Web API and Store API client."""

from __future__ import annotations

import json
import logging
from typing import Any, Protocol
from urllib.parse import urlencode

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from steam_library_monitor.models import AppInfo, OwnedGame

LOGGER = logging.getLogger(__name__)
STORE_URL = "https://store.steampowered.com/app/{app_id}/"

# Retry up to 5 times with exponential backoff: 1, 2, 4, 8, 16 seconds.
# Covers transient failures and rate-limit responses (429) from Steam APIs.
_RETRY_TOTAL = 5
_RETRY_BACKOFF_FACTOR = 1
_RETRY_STATUS_FORCELIST = (429, 500, 502, 503, 504)


def _make_default_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=_RETRY_TOTAL,
        backoff_factor=_RETRY_BACKOFF_FACTOR,
        status_forcelist=_RETRY_STATUS_FORCELIST,
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


class JsonResponse(Protocol):
    """Response surface used by this client."""

    def raise_for_status(self) -> None: ...

    def json(self) -> dict[str, Any]: ...


class HttpSession(Protocol):
    """Session surface used by this client."""

    def get(self, url: str, params: dict[str, str], timeout: int) -> JsonResponse: ...


class SteamClient:
    """Client for the Steam APIs used by the monitor."""

    def __init__(
        self,
        api_key: str,
        session: HttpSession | None = None,
        timeout: int = 30,
    ) -> None:
        self.api_key = api_key
        self.session = session or _make_default_session()
        self.timeout = timeout

    def _raise_for_status(self, response: JsonResponse) -> None:
        """Raise HTTPError for bad responses, with the API key redacted from the message."""
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            sanitized = str(exc).replace(self.api_key, "<redacted>")
            raise requests.HTTPError(sanitized) from None

    def get_owned_games(self, steam_id: str) -> list[OwnedGame]:
        """Fetch visible owned games for a Steam account."""

        url = "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"
        params: dict[str, str] = {
            "key": self.api_key,
            "steamid": steam_id,
            "include_appinfo": "true",
            "include_played_free_games": "true",
        }
        LOGGER.debug("Requesting owned games: %s?%s", url, redact_query(params))
        response = self.session.get(url, params=params, timeout=self.timeout)
        self._raise_for_status(response)
        payload = response.json()
        games = payload.get("response", {}).get("games", [])
        parsed: list[OwnedGame] = []
        for game in games:
            app_id = game.get("appid")
            name = game.get("name")
            if app_id is None or not name:
                LOGGER.debug("Skipping owned game with missing appid/name: %s", game)
                continue
            parsed.append(OwnedGame(app_id=int(app_id), title=str(name)))
        LOGGER.debug("Owned app IDs for %s: %s", steam_id, [game.app_id for game in parsed])
        return parsed

    def get_app_details(self, app_id: int, fallback_title: str) -> AppInfo:
        """Fetch and classify app details from the Steam Store API."""

        url = "https://store.steampowered.com/api/appdetails"
        params = {"appids": str(app_id)}
        LOGGER.debug("Requesting app details: %s?%s", url, urlencode(params))
        response = self.session.get(url, params=params, timeout=self.timeout)
        self._raise_for_status(response)
        payload = response.json()
        app_payload = payload.get(str(app_id), {})
        if not app_payload.get("success"):
            LOGGER.debug("No appdetails data for app_id=%s", app_id)
            return AppInfo(
                app_id=app_id,
                title=fallback_title,
                app_type=None,
                store_url=STORE_URL.format(app_id=app_id),
                raw_json=json.dumps(app_payload, sort_keys=True),
            )

        data: dict[str, Any] = app_payload.get("data") or {}
        app_type = data.get("type")
        fullgame_value = data.get("fullgame")
        fullgame: dict[str, Any] = fullgame_value if isinstance(fullgame_value, dict) else {}
        base_app_id = fullgame.get("appid")
        base_title = fullgame.get("name")
        title = str(data.get("name") or fallback_title)
        LOGGER.debug(
            "Classified app_id=%s title=%r type=%r base=%r",
            app_id,
            title,
            app_type,
            base_title,
        )
        return AppInfo(
            app_id=app_id,
            title=title,
            app_type=str(app_type) if app_type else None,
            store_url=STORE_URL.format(app_id=app_id),
            base_app_id=int(base_app_id) if base_app_id is not None else None,
            base_title=str(base_title) if base_title else None,
            raw_json=json.dumps(app_payload, sort_keys=True),
        )


def redact_query(params: dict[str, str]) -> str:
    """Return a URL query string with secrets redacted."""

    redacted = {key: ("<redacted>" if key == "key" else value) for key, value in params.items()}
    return urlencode(redacted)
