"""Discord Cog to remind people to use inclusive language."""

import logging
import re
import time
from typing import cast, Sequence

import discord
import prometheus_client  # type: ignore
from discord.ext import commands

from cogs import base_cog

logger = logging.getLogger(__name__)

TITLE = "Inclusive Language Reminder!"
DURATION = 120


class InclusiveLanguage(base_cog.BaseCog):
    """Respond to posts with inclusivity reminders."""

    qualified_name = "Inclusive Language"
    STATS_TYPE = list

    def __init__(
        self,
        *,
        message: str,
        patterns: Sequence[re.Pattern],
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.message = message
        self.patterns = patterns
        self.prom_counter = prometheus_client.Counter(
            "inclusive_language_triggered", "How many times inclusive language was triggered."
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Add Emoji reactions on a new message."""
        channel = message.channel
        if message.author.bot:
            return
        if channel is None:
            return
        if not any(pattern.search(message.content) for pattern in self.patterns):
            return
        self.usage_stats[message.author.display_name].append(int(time.time()))
        self.prom_counter.inc()
        if channel.type == discord.ChannelType.public_thread:
            await message.reply(self.message, delete_after=DURATION, suppress_embeds=True)
        elif channel.type == discord.ChannelType.text:
            typed_channel = cast(discord.TextChannel, channel)
            thread = await typed_channel.create_thread(
                name=TITLE, auto_archive_duration=60
            )
            content = f"{message.author.mention} {self.message}\n\n{message.jump_url}"
            await thread.send(content=content, suppress_embeds=True)
