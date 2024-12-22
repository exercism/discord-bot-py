"""Discord Cog to close support threads."""

import asyncio
import datetime
import logging

import discord
import prometheus_client  # type: ignore
from discord.ext import commands
from discord.ext import tasks

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

        self.task_close_old_support.start()  # pylint: disable=E1101

    @commands.Cog.listener()
    async def on_thread_update(self, before, after) -> None:
        """On thread archive, lock a thread."""
        del before  # unused
        if after.parent.id != self.support_channel:
            return
        if not after.archived or after.locked:
            return
        logger.debug("Locking thread %d due to thread archival.", after.id)
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

        logger.debug("Locking thread %d due to owner resolving it.", payload.channel_id)
        await thread.edit(locked=True, archived=True)
        PROM_CLOSED.inc()

    @tasks.loop(minutes=60 * 11)
    async def task_close_old_support(self) -> None:
        """Close old support threads."""
        guild = self.bot.get_guild(self.exercism_guild_id)
        if not guild:
            logger.error("Failed to find the guild.")
            return
        channel = guild.get_channel(self.support_channel)
        if not channel or not isinstance(channel, discord.ForumChannel):
            logger.error("Failed to find the guild.")
            return
        count = 0
        cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=21)
        oldest = None
        for thread in channel.threads:
            if thread.archived or thread.locked:
                continue
            message_id = thread.last_message_id
            if not isinstance(message_id, int):
                continue
            try:
                last = await thread.fetch_message(message_id)
            except discord.errors.NotFound:
                continue
            if not last:
                continue
            oldest = min(last.created_at, oldest) if oldest else last.created_at  # type: ignore
            if last.created_at > cutoff:
                continue
            count += 1
            await thread.edit(locked=True, archived=True)
            PROM_CLOSED.inc()
            logger.debug("Locking thread: %s", last.content)
            await asyncio.sleep(1)

    @task_close_old_support.before_loop
    async def before_close_old_support(self):
        """Before starting the task, wait for bot ready."""
        await self.bot.wait_until_ready()
