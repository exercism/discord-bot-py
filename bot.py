#!/bin/python

import logging
import os
import sys
from typing import Any, Iterable, Sequence

import click
import conf
import discord
import dotenv
import mentor_requests
import mod_message
import track_react
from discord.ext import commands


class Bot(commands.Bot):

    def __init__(
        self,
        *args,
        exercism_guild_id: int,
        cogs: Sequence[commands.Cog],
        debug: bool,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.cogs_to_load = cogs
        self.exercism_guild_id = exercism_guild_id
        self.debug = debug

    async def setup_hook(self):
        """Configure the bot with various Cogs."""
        guild = discord.Object(id=self.exercism_guild_id)
        for cog, kwargs in self.cogs_to_load:
            await self.add_cog(cog(self, debug=self.debug, **kwargs), guild=guild)


def find_setting(key: str) -> str:
    if key in os.environ:
        return os.environ[key]
    if hasattr(conf, key):
        return getattr(conf, key)
    raise ValueError(f"Unable to find value for setting {key}")


def get_cogs(modules: Sequence[str] | None) -> list[commands.Cog]:
    cogs = [
        (
            mentor_requests.RequestNotifier,
            {
                "channel_id": int(find_setting("MENTOR_REQUEST_CHANNEL")),
                "sqlite_db": os.environ["MENTOR_REQUEST_DB"],
                "tracks": None,
            }
        ),
        (mod_message.ModMessage, {"canned_messages": conf.CANNED_MESSAGES}),
        (
            track_react.TrackReact,
            {"aliases": conf.ALIASES, "case_sensitive": conf.CASE_SENSITIVE}
        ),
    ]
    if modules:
        cogs = [(cog, kwargs) for cog, kwargs in cogs if cog.__name__ in modules]
    return cogs


def log_config(debug: bool) -> dict[str, Any]:
    config = {}
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
    dotenv.load_dotenv()

    intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True

    if "DISCORD_TOKEN" not in os.environ:
        raise RuntimeError("Missing DISCORD_TOKEN")

    bot = Bot(
        command_prefix="!",
        intents=intents,
        cogs=get_cogs(modules),
        debug=debug,
        exercism_guild_id=int(find_setting("GUILD_ID")),
    )
    bot.run(os.environ["DISCORD_TOKEN"], **log_config(debug))


if __name__ == "__main__":
    main()
