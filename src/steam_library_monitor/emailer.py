"""Email digest rendering and SMTP delivery."""

from __future__ import annotations

import smtplib
from collections import defaultdict
from collections.abc import Iterable
from email.message import EmailMessage

from steam_library_monitor.models import NewApp


def render_digest(items: Iterable[NewApp]) -> str:
    """Render a plain-text digest body."""

    grouped: dict[str, list[NewApp]] = defaultdict(list)
    for item in items:
        grouped[item.display_name].append(item)

    lines = ["Steam Library Monitor found new library additions.", ""]
    for display_name in sorted(grouped):
        lines.extend([f"## {display_name}", ""])
        account_items = grouped[display_name]
        games = [item for item in account_items if item.app.app_type == "game"]
        dlc = [item for item in account_items if item.app.app_type == "dlc"]
        other = [item for item in account_items if item.app.app_type not in {"game", "dlc"}]
        if games:
            lines.extend(["Games:", *(_render_app_bullet(item) for item in games), ""])
        if dlc:
            lines.extend(["DLC:"])
            for item in dlc:
                lines.append(f"- {item.app.title}")
                lines.append(f"  {item.app.store_url}")
                lines.append(f"  Base game: {item.app.base_title or 'Base game unknown'}")
            lines.append("")
        if other:
            lines.extend(["Other:", *(_render_app_bullet(item) for item in other), ""])
    return "\n".join(lines).rstrip() + "\n"


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
    message.set_content(render_digest(items))
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


def _render_app_bullet(item: NewApp) -> str:
    return f"- {item.app.title}\n  {item.app.store_url}"
