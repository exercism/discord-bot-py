"""Common Cog Code."""

import collections
from typing import Any, Callable

from discord.ext import commands


class BaseCog(commands.Cog):
    """Base Cog."""

    STATS_TYPE: Callable = int

    def __init__(
        self,
        bot: commands.Bot,
        debug: bool,
        exercism_guild_id: int,
    ) -> None:
        self.bot = bot
        self.debug = debug
        self.exercism_guild_id = exercism_guild_id
        self.usage_stats: dict[str, Any] = collections.defaultdict(self.STATS_TYPE)

    def details(self) -> str:
        """Return cog details."""
        return str(dict(self.usage_stats))
