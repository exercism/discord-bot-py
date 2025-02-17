#!/bin/python
"""A Discord bot for Exercism."""

# Standard Library
import logging
import os
import pathlib
import sys
from typing import Any, Iterable

# Third party
import click
import discord
import dotenv
import logging_loki  # type: ignore
import prometheus_client  # type: ignore
import sentry_sdk  # type: ignore
import systemd.journal  # type: ignore
from discord.ext import commands

# Local
import conf
import cogs
import webapp

logger = logging.getLogger("exercism_discord_bot")


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
        cogs_to_load: Iterable[str] | None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.cogs_to_load = cogs_to_load
        self.exercism_guild_id = exercism_guild_id
        self.gauge_cogs_loaded = prometheus_client.Gauge("cogs_loaded", "Number of cogs running")

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
        guild = discord.Object(id=self.exercism_guild_id)
        standard_args = {
            "bot": self,
            "exercism_guild_id": self.exercism_guild_id,
        }
        for cog, kwargs in self.get_cogs().items():
            combined = standard_args | kwargs
            logger.info("Loading cog %s", cog.__name__)
            instance = cog(**combined)
            await self.add_cog(instance, guild=guild)
            self.gauge_cogs_loaded.inc()

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
            cogs.CloseSupportThread: {
                "resolved_reaction": conf.SUPPORT_RESOLVED,
                "support_channel": conf.SUPPORT_CHANNEL,
            },
            cogs.InclusiveLanguage: {
                "pattern_response": conf.EXCLUSIVE_LANGUAGE
            },
            cogs.ModMessage: {"canned_messages": conf.CANNED_MESSAGES},
            cogs.PinnedMessage: {"messages": conf.PINNED_MESSAGES},
            cogs.RequestNotifier: {
                "channel_id": int(find_setting("MENTOR_REQUEST_CHANNEL")),
                "sqlite_db": find_setting("SQLITE_DB"),
                "tracks": None,
            },
            cogs.StreamingEvents: {
                "default_location_url": conf.DEFAULT_STREAMING_URL,
                "sqlite_db": find_setting("SQLITE_DB"),
            },
            cogs.ThreadReminder: {
                "channels": conf.THREAD_REMINDER_CHANNELS,
            },
            cogs.TrackReact: {
                "aliases": conf.ALIASES,
                "case_sensitive": conf.CASE_SENSITIVE,
                "no_react_channels": conf.NO_REACT_CHANNELS,
            },
        }
        # Optionally filter Cogs.
        if self.cogs_to_load:
            have = {cog.__name__ for cog in my_cogs}
            unmatched = set(self.cogs_to_load) - have
            if unmatched:
                logger.warning("Cogs are not found. Want %r; have %r.", unmatched, have)
            my_cogs = {
                cog: kwargs
                for cog, kwargs in my_cogs.items()
                if cog.__name__ in self.cogs_to_load
            }
        return my_cogs


def log_config(
    debug_modules: Iterable[str] | None,
    debug: bool,
) -> dict[str, Any]:
    """Return log configuration values."""
    # Configure logging.
    discord.utils.setup_logging()
    if debug:
        logger.root.setLevel(logging.DEBUG)
    for module in ("discord.client", "discord.gateway", "discord.http"):
        logging.getLogger(module).setLevel(logging.WARNING)
    for module in debug_modules or []:
        logging.getLogger(module).setLevel(logging.DEBUG)

    # Configure Grafana Loki logging.
    grafana_handler = None
    if has_setting("GRAFANA_USER") and has_setting("GRAFANA_KEY"):
        grafana_auth = find_setting("GRAFANA_USER") + ":" + find_setting("GRAFANA_KEY")
        grafana_url = f"https://{grafana_auth}@logs-prod-017.grafana.net/loki/api/v1/push"
        grafana_handler = logging_loki.LokiHandler(
            url=grafana_url,
            version="1",
            tags={"service": "exercism-discord-bot"},
        )
        logger.addHandler(grafana_handler)

    config: dict[str, Any] = {}
    if sys.stdout.isatty():
        log_stream = sys.stdout
        config["log_handler"] = logging.StreamHandler(stream=log_stream)
    else:
        log_stream = sys.stderr
        # Log to journald
        logger.root.addHandler(
            systemd.journal.JournalHandler(SYSLOG_IDENTIFIER="exercism_discord")
        )
        for handler in logger.root.handlers:
            if isinstance(handler, logging.StreamHandler):
                logger.root.removeHandler(handler)

    if sys.stdout.isatty():
        config["log_level"] = logging.INFO
    else:
        config["log_level"] = logging.WARNING
    return config


@click.command()
@click.option("--debug/--no-debug", default=False)
@click.option("--cogs-to-load", "--cogs", required=False, type=str, multiple=True)
@click.option("--debug_modules", required=False, type=str, multiple=True)
@click.option(
    "--config",
    required=False,
    type=click.Path(exists=True, dir_okay=False, path_type=pathlib.Path),
)
def main(
    debug: bool,
    cogs_to_load: Iterable[str] | None,
    debug_modules: Iterable[str] | None,
    config: pathlib.Path | None,
) -> None:
    """Run the Discord bot."""
    # Find a config file and load values.
    dotenv_loaded = False
    if config:
        config_file = config
    else:
        config_file = pathlib.Path(os.getenv("CONFIGURATION_DIRECTORY", "/etc"))
        config_file /= "exercism_discord.conf"
    if config_file.exists():
        dotenv_loaded = dotenv.load_dotenv(config_file)
        if dotenv_loaded:
            logger.info("Loaded config from %s", config_file)
    # Fall back to ./.env
    if not dotenv_loaded:
        dotenv_loaded = dotenv.load_dotenv()
        if dotenv_loaded:
            logger.info("Loaded config from .env")
        else:
            logger.warning("Did not load config into the env")

    if not has_setting("DISCORD_TOKEN"):
        raise RuntimeError("Missing DISCORD_TOKEN")

    if find_setting("PROMETHEUS_PORT"):
        prometheus_client.start_http_server(int(find_setting("PROMETHEUS_PORT")))

    # Start the bot.
    intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True
    intents.reactions = True

    bot = Bot(
        command_prefix="!",
        intents=intents,
        cogs_to_load=cogs_to_load or conf.COGS,
        exercism_guild_id=int(find_setting("GUILD_ID")),
    )
    bot.run(find_setting("DISCORD_TOKEN"), **log_config(debug_modules, debug))


if __name__ == "__main__":
    main()  # pylint: disable=E1120
