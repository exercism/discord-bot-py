#!/bin/python
"""A Discord bot for Exercism."""

# Standard Library
import logging
import os
import pathlib
import re
import sys
from typing import Any, Iterable

# Third party
import click
import discord
import dotenv
import logging_loki  # type: ignore
import sentry_sdk  # type: ignore
from discord.ext import commands

# Local
import conf
import cogs
import webapp

logger = logging.getLogger()


def has_setting(key: str) -> bool:
    """Return if a setting is defined."""
    try:
        find_setting(key)
    except ValueError:
        return False
    return True


def find_setting(key: str) -> str:
    """Return a setting value, checking first the env then the config file."""
    if key in os.environ:
        return os.environ[key]
    if hasattr(conf, key):
        return getattr(conf, key)
    raise ValueError(f"Unable to find value for setting {key}")


class Bot(commands.Bot):
    """Exercism Discord Bot."""

    def __init__(
        self,
        *args,
        exercism_guild_id: int,
        modules: Iterable[str] | None,
        debug: bool,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.modules_to_load = modules
        self.exercism_guild_id = exercism_guild_id
        self.debug = debug

    async def setup_hook(self):
        """Configure the bot with various Cogs."""
        # Start the Web Application.
        if has_setting("WEBAPP_HOST") and has_setting("WEBAPP_PORT"):
            host = find_setting("WEBAPP_HOST")
            port = int(find_setting("WEBAPP_PORT"))
            await webapp.WebApp(bot=self).start_web(host=host, port=port)

        # Configure sentry.io monitoring.
        if has_setting("SENTRY_URI"):
            sentry_sdk.init(
                dsn=find_setting("SENTRY_URI"),
                traces_sample_rate=1.0,
            )
        # Configure Grafana Loki logging.
        if has_setting("GRAFANA_USER") and has_setting("GRAFANA_KEY"):
            grafana_auth = find_setting("GRAFANA_USER") + ":" + find_setting("GRAFANA_KEY")
            grafana_url = f"https://{grafana_auth}@logs-prod-017.grafana.net/loki/api/v1/push"
            grafana_handler = logging_loki.LokiHandler(
                url=grafana_url,
                version="1",
                tags={"service": "exercism-discord-bot"},
            )
            logger.addHandler(grafana_handler)

        guild = discord.Object(id=self.exercism_guild_id)
        standard_args = {
            "bot": self,
            "debug": self.debug,
            "exercism_guild_id": self.exercism_guild_id,
            "handler": grafana_handler,
        }
        for cog, kwargs in self.get_cogs().items():
            combined = standard_args | kwargs
            logger.info("Loading cog %s", cog.__name__)
            instance = cog(**combined)
            await self.add_cog(instance, guild=guild)

    async def on_error(self, event_method, /, *args, **kwargs) -> None:
        """Capture and log errors."""
        _, err, traceback = sys.exc_info()
        logger.error(  # pylint: disable=W1203
            f"Exception thrown. {event_method=}, {args=}, {kwargs}, {err=}, {traceback=}"
        )
        sentry_sdk.capture_exception()

    def get_cogs(self) -> dict[commands.CogMeta, dict[str, Any]]:
        """Return the Cogs to load."""
        my_cogs: dict[commands.CogMeta, dict[str, Any]] = {
            cogs.InclusiveLanguage: {
                "patterns": [re.compile(r, re.IGNORECASE) for r in conf.EXCLUSIVE_LANGUAGE]
            },
            cogs.ModMessage: {"canned_messages": conf.CANNED_MESSAGES},
            cogs.RequestNotifier: {
                "channel_id": int(find_setting("MENTOR_REQUEST_CHANNEL")),
                "sqlite_db": find_setting("SQLITE_DB"),
                "tracks": None,
            },
            cogs.StreamingEvents: {
                "default_location_url": conf.DEFAULT_STREAMING_URL,
                "sqlite_db": find_setting("SQLITE_DB"),
            },
            cogs.TrackReact: {"aliases": conf.ALIASES, "case_sensitive": conf.CASE_SENSITIVE},
        }
        # Optionally filter Cogs.
        if self.modules_to_load:
            my_cogs = {
                cog: kwargs
                for cog, kwargs in my_cogs.items()
                if cog.__name__ in self.modules_to_load
            }
        return my_cogs


def log_config() -> dict[str, Any]:
    """Return log configuration values."""
    config: dict[str, Any] = {}
    if sys.stdout.isatty():
        log_stream = sys.stdout
    else:
        log_stream = sys.stderr
    config["log_handler"] = logging.StreamHandler(stream=log_stream)

    if sys.stdout.isatty():
        config["log_level"] = logging.INFO
    else:
        config["log_level"] = logging.WARNING
    return config


@click.command()
@click.option("--debug/--no-debug", default=False)
@click.option("--modules", required=False, type=str, multiple=True)
def main(debug: bool, modules: Iterable[str] | None) -> None:
    """Run the Discord bot."""
    discord.utils.setup_logging()
    logging.getLogger("discord.gateway").setLevel(logging.WARNING)

    # Try to load environment vars from /etc/exercism_discord.conf if possible.
    dotenv_loaded = False
    config = pathlib.Path(os.getenv("CONFIGURATION_DIRECTORY", "/etc"))
    config /= "exercism_discord.conf"
    if config.exists():
        dotenv_loaded = dotenv.load_dotenv(config)
        if dotenv_loaded:
            logger.info("Loaded config from %s", config)
    # Fall back to ./.env
    if not dotenv_loaded:
        dotenv_loaded = dotenv.load_dotenv()
        if dotenv_loaded:
            logger.info("Loaded config from .env")
        else:
            logger.warning("Did not load config into the env")

    intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True

    if not has_setting("DISCORD_TOKEN"):
        raise RuntimeError("Missing DISCORD_TOKEN")

    bot = Bot(
        command_prefix="!",
        intents=intents,
        modules=modules or conf.MODULES,
        debug=debug,
        exercism_guild_id=int(find_setting("GUILD_ID")),
    )
    bot.run(find_setting("DISCORD_TOKEN"), **log_config())


if __name__ == "__main__":
    main()  # pylint: disable=E1120
