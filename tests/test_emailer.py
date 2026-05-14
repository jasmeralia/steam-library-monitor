from __future__ import annotations

from steam_library_monitor.emailer import build_message, render_digest
from steam_library_monitor.models import AppInfo, NewApp


def new_app(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    display_name: str,
    app_id: int,
    title: str,
    app_type: str,
    base_title: str | None = None,
    release_year: int | None = None,
) -> NewApp:
    return NewApp(
        steam_id="76561198000000001",
        display_name=display_name,
        app=AppInfo(
            app_id=app_id,
            title=title,
            app_type=app_type,
            store_url=f"https://store.steampowered.com/app/{app_id}/",
            base_title=base_title,
            release_year=release_year,
        ),
    )


def test_app_info_cover_url() -> None:
    app = AppInfo(
        app_id=570,
        title="Dota 2",
        app_type="game",
        store_url="https://store.steampowered.com/app/570/",
    )

    assert app.cover_url == "https://cdn.akamai.steamstatic.com/steam/apps/570/header.jpg"


def test_render_digest_groups_by_account_and_type() -> None:
    body = render_digest(
        [
            new_app("Alice", 10, "Example Game", "game"),
            new_app("Alice", 20, "Example DLC", "dlc", "Example Game"),
        ]
    )

    assert "<h2>Alice</h2>" in body
    assert "<h3>Games</h3>" in body
    assert 'href="https://store.steampowered.com/app/10/"' in body
    assert ">Example Game</a>" in body
    assert "<h3>DLC</h3>" in body
    assert 'href="https://store.steampowered.com/app/20/"' in body
    assert ">Example DLC</a>" in body
    assert "Base game: Example Game" in body


def test_render_digest_uses_unknown_base_game_text() -> None:
    body = render_digest([new_app("Alice", 20, "Example DLC", "dlc")])

    assert "Base game: Base game unknown" in body


def test_render_digest_escapes_html() -> None:
    body = render_digest([new_app("Alice & Bob", 10, "<Example Game>", "game")])

    assert "Alice &amp; Bob" in body
    assert "&lt;Example Game&gt;" in body
    assert "<Example Game>" not in body


def test_render_digest_includes_cover_art() -> None:
    body = render_digest([new_app("Alice", 10, "Example Game", "game")])

    assert 'src="https://cdn.akamai.steamstatic.com/steam/apps/10/header.jpg"' in body
    assert 'alt="Example Game"' in body
    assert 'width="100%"' in body


def test_render_digest_shows_release_year() -> None:
    body = render_digest([new_app("Alice", 10, "Example Game", "game", release_year=2023)])

    assert "2023" in body


def test_render_digest_omits_year_when_unknown() -> None:
    body = render_digest([new_app("Alice", 10, "Example Game", "game")])

    assert "release_year" not in body


def test_render_digest_uses_grid_table() -> None:
    body = render_digest([new_app("Alice", i, f"Game {i}", "game") for i in range(1, 5)])

    assert "<table" in body
    assert "<td" in body


def test_build_message_returns_none_when_no_items() -> None:
    assert build_message([], "sender@example.com", "to@example.com") is None


def test_build_message_uses_html_body() -> None:
    message = build_message(
        [new_app("Alice", 10, "Example Game", "game")],
        "sender@example.com",
        "to@example.com",
    )

    assert message is not None
    assert message["Subject"] == "Steam Library Monitor: 1 new item(s)"
    assert message.get_content_type() == "text/html"
    assert not message.is_multipart()
    assert "<html" in message.get_content()
