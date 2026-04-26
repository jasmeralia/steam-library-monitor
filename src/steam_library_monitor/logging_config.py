"""Logging setup."""

from __future__ import annotations

import logging


def configure_logging(level: str) -> None:
    """Configure root logging."""

    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
