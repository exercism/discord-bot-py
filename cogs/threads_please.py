"""Discord Cog to remind people to use threads."""

import logging
from typing import cast

import discord
import prometheus_client  # type: ignore
from discord.ext import commands

from cogs import base_cog

logger = logging.getLogger(__name__)

TITLE = "Reminder: Please Use Threads"
REMINDER = (
    "Hi there 👋\n"
    "You just replied to a message in the main channel, rather than in a thread. "
    "We're quite strict on using threads to keep things tidy in this channel. "
    "Please could you copy/paste your message to a thread, "
    "and delete the message from the main channel.\n"
    "Thank you! 🙂"
)
DURATION = 120


class ThreadReminder(base_cog.BaseCog):
    """Reminds people using "reply to" to use threads."""

    qualified_name = "ThreadReminder"

    def __init__(
        self,
        *,
        channels: list[int],
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.channels = channels
        self.prom_counter = prometheus_client.Counter(
            "thread_reminder", "How many times thread reminder was triggered."
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """React to non-threaded responses with a reminder."""
        channel = message.channel
        if message.author.bot or message.type != discord.MessageType.reply:
            return
        if channel is None or channel.type != discord.ChannelType.text:
            return
        if channel.id not in self.channels:
            return

        self.usage_stats[message.author.display_name] += 1
        self.prom_counter.inc()
        typed_channel = cast(discord.TextChannel, channel)
        thread = await typed_channel.create_thread(name=TITLE, auto_archive_duration=60)
        content = f"{message.author.mention} {REMINDER}\n\n{message.jump_url}"
        await thread.send(content=content, suppress_embeds=True)
