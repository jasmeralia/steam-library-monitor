"""Command-line entrypoint."""

from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv

from steam_library_monitor.app import SteamLibraryMonitor
from steam_library_monitor.config import ConfigError, load_config
from steam_library_monitor.logging_config import configure_logging

_TRUTHY_VALUES = {"1", "true", "yes", "on"}


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(prog="steam-library-monitor")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single poll cycle and exit instead of polling forever.",
    )
    return parser.parse_args(argv)


def _env_flag_set(value: str | None) -> bool:
    """Return whether an environment flag value should be treated as truthy."""

    return (value or "").strip().lower() in _TRUTHY_VALUES


def main(argv: list[str] | None = None) -> int:
    """Run the service."""
    load_dotenv()
    args = _parse_args(argv)
    run_once = args.once or _env_flag_set(os.environ.get("RUN_ONCE"))

    try:
        config = load_config()
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    configure_logging(config.log_level)

    monitor = SteamLibraryMonitor(config)
    if run_once:
        monitor.initialize()
        monitor.poll_once()
    else:
        monitor.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
