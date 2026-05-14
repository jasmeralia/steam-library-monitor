"""Email digest rendering and SMTP delivery."""

from __future__ import annotations

import smtplib
from collections import defaultdict
from collections.abc import Iterable
from email.message import EmailMessage
from html import escape

from steam_library_monitor.models import NewApp

_GRID_COLUMNS = 3
_COL_WIDTH = f"{100 // _GRID_COLUMNS}%"


def render_digest(items: Iterable[NewApp]) -> str:
    """Render an HTML digest body."""

    grouped: dict[str, list[NewApp]] = defaultdict(list)
    for item in items:
        grouped[item.display_name].append(item)

    sections = []
    for display_name in sorted(grouped):
        account_items = grouped[display_name]
        games = [item for item in account_items if item.app.app_type == "game"]
        dlc = [item for item in account_items if item.app.app_type == "dlc"]
        other = [item for item in account_items if item.app.app_type not in {"game", "dlc"}]
        section_parts = [f"<h2>{escape(display_name)}</h2>"]
        if games:
            section_parts.append(_render_app_group("Games", games))
        if dlc:
            section_parts.append(_render_app_group("DLC", dlc, include_base_game=True))
        if other:
            section_parts.append(_render_app_group("Other", other))
        sections.append(f"<section>{''.join(section_parts)}</section>")

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: Arial, sans-serif; color: #202124; line-height: 1.45; }}
    h1 {{ font-size: 20px; margin: 0 0 16px; }}
    h2 {{ font-size: 16px; margin: 24px 0 8px; }}
    h3 {{ font-size: 14px; margin: 16px 0 8px; }}
    a {{ color: #1a73e8; }}
    .metadata {{ color: #5f6368; font-size: 13px; margin-top: 2px; }}
  </style>
</head>
<body>
  <h1>Steam Library Monitor found new library additions.</h1>
  {"".join(sections)}
</body>
</html>
"""


def build_message(
    items: list[NewApp],
    sender: str,
    recipient: str,
) -> EmailMessage | None:
    """Build a digest email, or None when there are no items."""

    if not items:
        return None
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = f"Steam Library Monitor: {len(items)} new item(s)"
    message.set_content(render_digest(items), subtype="html")
    return message


class Emailer:
    """SMTP email sender."""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        smtp_username: str,
        smtp_password: str,
    ) -> None:
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_username = smtp_username
        self.smtp_password = smtp_password

    def send(self, message: EmailMessage) -> None:
        """Send an email message over STARTTLS SMTP."""

        with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(self.smtp_username, self.smtp_password)
            smtp.send_message(message)


def _render_app_group(
    heading: str,
    items: list[NewApp],
    *,
    include_base_game: bool = False,
) -> str:
    grid = _render_grid(items, include_base_game)
    return f"<h3>{escape(heading)}</h3>{grid}"


def _render_grid(items: list[NewApp], include_base_game: bool) -> str:
    cells = [_render_card(item, include_base_game) for item in items]
    remainder = len(cells) % _GRID_COLUMNS
    if remainder:
        cells.extend(
            [f'<td width="{_COL_WIDTH}" style="width:{_COL_WIDTH};padding:6px;"></td>']
            * (_GRID_COLUMNS - remainder)
        )
    rows = [
        f"<tr>{''.join(cells[i : i + _GRID_COLUMNS])}</tr>"
        for i in range(0, len(cells), _GRID_COLUMNS)
    ]
    return (
        '<table width="100%" cellpadding="0" cellspacing="0" role="presentation"'
        ' style="border-collapse:collapse;">' + "".join(rows) + "</table>"
    )


def _render_card(item: NewApp, include_base_game: bool) -> str:
    title = escape(item.app.title)
    store_url = escape(item.app.store_url, quote=True)
    cover_url = escape(item.app.cover_url, quote=True)
    meta_parts: list[str] = [
        f'<div style="font-weight:700;font-size:14px;">'
        f'<a href="{store_url}" style="color:#202124;text-decoration:none;">{title}</a>'
        f"</div>",
    ]
    if item.app.release_year is not None:
        meta_parts.append(
            f'<div style="color:#5f6368;font-size:12px;margin-top:3px;">'
            f"{item.app.release_year}</div>"
        )
    if include_base_game:
        base_title = escape(item.app.base_title or "Base game unknown")
        meta_parts.append(f'<div class="metadata">Base game: {base_title}</div>')
    return (
        f'<td width="{_COL_WIDTH}" style="width:{_COL_WIDTH};padding:6px;vertical-align:top;">'
        '<div style="border:2px solid #dadce0;border-radius:8px;overflow:hidden;">'
        f'<a href="{store_url}" style="display:block;line-height:0;">'
        f'<img src="{cover_url}" alt="{title}" width="100%"'
        f' style="display:block;border:0;width:100%;" /></a>'
        '<div style="padding:8px 10px;">' + "".join(meta_parts) + "</div></div></td>"
    )
