#!/bin/python
"""A Discord bot for Exercism."""

# Standard Library
import logging
import os
import sys
from typing import Any, Iterable

# Third party
import click
import discord
import dotenv
from discord.ext import commands

# Local
import conf
import mentor_requests
import mod_message
import streaming_events
import track_react


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
        guild = discord.Object(id=self.exercism_guild_id)
        standard_args = {"debug": self.debug, "exercism_guild_id": self.exercism_guild_id}
        for cog, kwargs in self.get_cogs():
            await self.add_cog(
                cog(self, **standard_args, **kwargs),
                guild=guild
            )

    def get_cogs(self) -> list[tuple[commands.CogMeta, dict[str, Any]]]:
        """Return a list of Cogs to load."""
        cogs: list[tuple[commands.CogMeta, dict[str, Any]]] = [
            (
                mentor_requests.RequestNotifier,
                {
                    "channel_id": int(find_setting("MENTOR_REQUEST_CHANNEL")),
                    "sqlite_db": os.environ["MENTOR_REQUEST_DB"],
                    "tracks": None,
                }
            ),
            (mod_message.ModMessage, {"canned_messages": conf.CANNED_MESSAGES}),
            (streaming_events.StreamingEvents, {"default_location_url": conf.DEFAULT_STREAMING_URL}),
            (
                track_react.TrackReact,
                {"aliases": conf.ALIASES, "case_sensitive": conf.CASE_SENSITIVE}
            ),
        ]
        # Optionally filter Cogs.
        if self.modules_to_load:
            cogs = [
                (cog, kwargs)
                for cog, kwargs in cogs
                if cog.__name__ in self.modules_to_load
            ]
        return cogs


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
    dotenv.load_dotenv()

    intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True

    if "DISCORD_TOKEN" not in os.environ:
        raise RuntimeError("Missing DISCORD_TOKEN")

    bot = Bot(
        command_prefix="!",
        intents=intents,
        modules=modules,
        debug=debug,
        exercism_guild_id=int(find_setting("GUILD_ID")),
    )
    bot.run(os.environ["DISCORD_TOKEN"], **log_config())


if __name__ == "__main__":
    main()  # pylint: disable=E1120
