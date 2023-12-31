"""Discord Cog to close support threads."""

import asyncio
import logging

import discord
import prometheus_client  # type: ignore
from discord.ext import commands

from cogs import base_cog

logger = logging.getLogger(__name__)
PROM_CLOSED = prometheus_client.Counter("close_support_thread", "Count closed support threads")


class CloseSupportThread(base_cog.BaseCog):
    """Close support threads when they are marked as resolved or time out."""

    qualified_name = "Close Support Thread"

    def __init__(
        self,
        resolved_reaction: str,
        support_channel: int,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.resolved_reaction = resolved_reaction
        self.support_channel = support_channel

    @commands.Cog.listener()
    async def on_thread_update(self, before, after) -> None:
        """On thread archive, lock a thread."""
        del before  # unused
        if after.parent.id != self.support_channel:
            return
        if not after.archived or after.locked:
            return
        logger.info("Locking thread %d due to thread archival.", after.id)
        await after.edit(archived=False)
        await asyncio.sleep(1)
        await after.edit(locked=True, archived=True)
        PROM_CLOSED.inc()

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload) -> None:
        """On a resolved reaction, lock a thread."""
        if (
            not payload.guild_id
            or not payload.member
            or payload.event_type != "REACTION_ADD"
            or not payload.emoji
            or payload.emoji.name != self.resolved_reaction
        ):
            return

        guild = self.bot.get_guild(self.exercism_guild_id)
        if not guild:
            logger.error("Failed to find the guild.")
            return

        thread = guild.get_thread(payload.channel_id)
        if (
            not isinstance(thread, discord.Thread)
            or not isinstance(thread.parent, discord.ForumChannel)
            or thread.parent.id != self.support_channel
            or thread.owner != payload.member
            or payload.channel_id != payload.message_id
        ):
            return

        logger.info("Locking thread %d due to owner resolving it.", payload.channel_id)
        await thread.edit(locked=True)
        PROM_CLOSED.inc()
