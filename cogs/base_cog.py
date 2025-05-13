"""Common Cog Code."""

import collections
from typing import Any, Callable

import pymongo.mongo_client  # type: ignore
from discord.ext import commands


class BaseCog(commands.Cog):
    """Base Cog."""

    STATS_TYPE: Callable = int

    def __init__(
        self,
        bot: commands.Bot,
        exercism_guild_id: int,
        mongodb: None | pymongo.mongo_client.MongoClient = None,
    ) -> None:
        self.bot = bot
        self.exercism_guild_id = exercism_guild_id
        self.usage_stats: dict[str, Any] = collections.defaultdict(self.STATS_TYPE)
        self.mongodb = mongodb

    def details(self) -> str:
        """Return cog details."""
        return str(dict(self.usage_stats))
