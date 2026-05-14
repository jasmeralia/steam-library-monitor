from __future__ import annotations

from typing import Any

import pytest
import requests

from steam_library_monitor.steam import SteamClient, redact_query


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self.payload


class FakeSession:
    def __init__(self, payloads: list[dict[str, Any]]) -> None:
        self.payloads = payloads
        self.calls: list[tuple[str, dict[str, str], int]] = []

    def get(self, url: str, params: dict[str, str], timeout: int) -> FakeResponse:
        self.calls.append((url, params, timeout))
        return FakeResponse(self.payloads.pop(0))


def test_builds_correct_owned_games_request() -> None:
    session = FakeSession([{"response": {"games": []}}])
    client = SteamClient("secret", session=session)

    client.get_owned_games("76561198000000001")

    url, params, _timeout = session.calls[0]
    assert url == "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"
    assert params["key"] == "secret"
    assert params["steamid"] == "76561198000000001"
    assert params["include_appinfo"] == "true"
    assert params["include_played_free_games"] == "true"


def test_redacts_api_key() -> None:
    query = redact_query({"key": "secret", "steamid": "123"})

    assert "secret" not in query
    assert "%3Credacted%3E" in query


def test_parses_owned_games_response() -> None:
    session = FakeSession([{"response": {"games": [{"appid": 10, "name": "Example Game"}]}}])
    client = SteamClient("secret", session=session)

    games = client.get_owned_games("76561198000000001")

    assert games[0].app_id == 10
    assert games[0].title == "Example Game"


def test_parses_appdetails_game_response() -> None:
    session = FakeSession(
        [{"10": {"success": True, "data": {"type": "game", "name": "Example Game"}}}]
    )
    client = SteamClient("secret", session=session)

    app = client.get_app_details(10, "Fallback")

    assert app.app_type == "game"
    assert app.title == "Example Game"
    assert app.release_year is None


def test_parses_release_year_from_appdetails() -> None:
    session = FakeSession(
        [
            {
                "10": {
                    "success": True,
                    "data": {
                        "type": "game",
                        "name": "Example Game",
                        "release_date": {"coming_soon": False, "date": "29 Mar, 2020"},
                    },
                }
            }
        ]
    )
    client = SteamClient("secret", session=session)

    app = client.get_app_details(10, "Fallback")

    assert app.release_year == 2020


def test_parses_appdetails_dlc_response_with_base_game() -> None:
    session = FakeSession(
        [
            {
                "20": {
                    "success": True,
                    "data": {
                        "type": "dlc",
                        "name": "Example DLC",
                        "fullgame": {"appid": "10", "name": "Example Game"},
                    },
                }
            }
        ]
    )
    client = SteamClient("secret", session=session)

    app = client.get_app_details(20, "Fallback")

    assert app.app_type == "dlc"
    assert app.base_app_id == 10
    assert app.base_title == "Example Game"


def test_api_key_redacted_in_http_error() -> None:
    class LeakyResponse:
        def raise_for_status(self) -> None:
            raise requests.HTTPError(
                "401 Client Error for url: https://api.steampowered.com/?key=super-secret"
            )

        def json(self) -> dict[str, Any]:
            return {}

    class LeakySession:
        def get(self, url: str, params: dict[str, str], timeout: int) -> LeakyResponse:  # pylint: disable=unused-argument
            return LeakyResponse()

    client = SteamClient("super-secret", session=LeakySession())

    with pytest.raises(requests.HTTPError) as exc_info:
        client.get_owned_games("12345")

    assert "super-secret" not in str(exc_info.value)
    assert "<redacted>" in str(exc_info.value)


@pytest.mark.parametrize("payload", [{}, {"30": {"success": False}}])
def test_handles_missing_appdetails_data_gracefully(payload: dict[str, Any]) -> None:
    session = FakeSession([payload])
    client = SteamClient("secret", session=session)

    app = client.get_app_details(30, "Fallback")

    assert app.app_id == 30
    assert app.title == "Fallback"
    assert app.app_type is None
