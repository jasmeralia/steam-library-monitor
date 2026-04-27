"""Application polling loop."""

from __future__ import annotations

import logging
import time

from steam_library_monitor.config import Config
from steam_library_monitor.db import Database
from steam_library_monitor.emailer import Emailer, build_message
from steam_library_monitor.models import AppInfo, NewApp, OwnedGame
from steam_library_monitor.steam import SteamClient

LOGGER = logging.getLogger(__name__)


class SteamLibraryMonitor:
    """Coordinates polling, persistence, and email notifications."""

    def __init__(
        self,
        config: Config,
        database: Database | None = None,
        steam_client: SteamClient | None = None,
        emailer: Emailer | None = None,
    ) -> None:
        self.config = config
        self.database = database or Database(config.database_path)
        self.steam_client = steam_client or SteamClient(config.steam_api_key)
        self.emailer = emailer or Emailer(
            config.smtp_host,
            config.smtp_port,
            config.smtp_username,
            config.smtp_password,
        )

    def initialize(self) -> None:
        """Initialize backing services."""

        self.database.initialize()

    def poll_once(self) -> list[NewApp]:  # pylint: disable=too-many-locals
        """Run one full polling cycle."""

        run_id = self.database.start_poll_run()
        LOGGER.info("Starting poll for %s configured user(s)", len(self.config.steam_users))
        try:
            new_items: list[NewApp] = []
            for user in self.config.steam_users:
                owned_games = self.steam_client.get_owned_games(user.steam_id)

                cache_hits: dict[int, AppInfo] = {}
                cache_misses: list[OwnedGame] = []
                for owned_game in owned_games:
                    cached = self.database.get_app(owned_game.app_id)
                    if cached is not None:
                        cache_hits[owned_game.app_id] = cached
                    else:
                        cache_misses.append(owned_game)
                LOGGER.info(
                    "%s owned game(s) for %s: %s cached, %s need API lookup",
                    len(owned_games),
                    user.display_name,
                    len(cache_hits),
                    len(cache_misses),
                )

                fetched: dict[int, AppInfo] = {}
                for owned_game in cache_misses:
                    time.sleep(self.config.appdetails_delay)
                    fetched_info = self.steam_client.get_app_details(
                        owned_game.app_id,
                        owned_game.title,
                    )
                    if fetched_info.app_type is not None:
                        self.database.cache_app(fetched_info)
                    fetched[owned_game.app_id] = fetched_info
                fetched_kept = sum(1 for a in fetched.values() if a.app_type in {"game", "dlc"})
                LOGGER.info(
                    "%s API lookup(s) complete: %s game/dlc, %s ignored",
                    len(cache_misses),
                    fetched_kept,
                    len(cache_misses) - fetched_kept,
                )

                app_infos: list[AppInfo] = []
                for owned_game in owned_games:
                    app_info = cache_hits.get(owned_game.app_id) or fetched.get(
                        owned_game.app_id
                    )
                    if app_info is None:
                        continue
                    if app_info.app_type in {"game", "dlc"}:
                        app_infos.append(app_info)
                    else:
                        LOGGER.debug(
                            "Ignoring app_id=%s with app_type=%r",
                            app_info.app_id,
                            app_info.app_type,
                        )
                account_new_items = self.database.sync_account_apps(user, app_infos)
                LOGGER.info(
                    "Poll found %s new item(s) for %s",
                    len(account_new_items),
                    user.display_name,
                )
                new_items.extend(account_new_items)
            message = build_message(new_items, self.config.sender, self.config.smtp_to)
            if message is not None:
                self.emailer.send(message)
                LOGGER.info("Sent digest email with %s new item(s)", len(new_items))
            self.database.finish_poll_run(run_id, "success", f"{len(new_items)} new item(s)")
            LOGGER.info("Finished poll with %s new item(s)", len(new_items))
            return new_items
        except Exception as exc:
            self.database.finish_poll_run(run_id, "error", str(exc))
            LOGGER.exception("Poll failed")
            raise

    def run_forever(self) -> None:
        """Run continuous polling."""

        self.initialize()
        LOGGER.info("Starting steam-library-monitor")
        while True:
            try:
                self.poll_once()
            except Exception:  # pylint: disable=broad-exception-caught
                LOGGER.error("Poll failed; will retry after sleep interval")
            LOGGER.debug("Sleeping for %s seconds", self.config.sleep_interval)
            time.sleep(self.config.sleep_interval)
