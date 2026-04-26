"""Command-line entrypoint."""

from __future__ import annotations

import sys

from steam_library_monitor.app import SteamLibraryMonitor
from steam_library_monitor.config import ConfigError, load_config
from steam_library_monitor.logging_config import configure_logging


def main() -> int:
    """Run the service."""

    try:
        config = load_config()
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    configure_logging(config.log_level)
    SteamLibraryMonitor(config).run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
