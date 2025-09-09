"""Discord Cog to detect spam."""

import collections
import logging
import time

import discord
import prometheus_client  # type: ignore
from discord.ext import commands

from cogs import base_cog

logger = logging.getLogger(__name__)

TITLE = "Spam Detector"
REPEATED = 4
DURATION = 10


class SpamDetector(base_cog.BaseCog):
    """Flag repeated messages posted in short succession."""

    qualified_name = TITLE
    STATS_TYPE = list

    def __init__(
        self,
        *,
        mod_channel: int,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.mod_channel = mod_channel
        self.prom_counter = prometheus_client.Counter(
            "spam_detected", "How many times spam was detected."
        )
        # timestamp => user => messages
        self.messages = collections.defaultdict(lambda: collections.defaultdict(list))
        self.guild = None
        self.mod_role_id = None

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Fetch data when ready."""
        guild = self.bot.get_guild(self.exercism_guild_id)
        assert guild is not None, "Could not find the guild."
        channel = guild.get_channel(self.mod_channel)
        assert isinstance(channel, discord.TextChannel), f"{channel} is not a TextChannel."

        self.mod_role_id = [r.id for r in guild.roles if "moderator" in r.name][0]
        self.mod_channel = channel
        self.guild = guild

    def message_match(self, one: discord.Message, two: discord.Message) -> bool:
        """Return if two messages match."""
        return (
            one.author == two.author
            and one.content == two.content
            and sorted(one.embeds) == sorted(two.embeds)
            and sorted(one.attachments) == sorted(two.attachments)
        )

    async def send_alert(self, message: discord.Message) -> None:
        """Send an alert about spam."""
        msg = f"<@&{self.mod_role_id}> Spam detected "
        msg += f"by {message.author.name} in {message.channel.name}: {message.jump_url}"
        await self.mod_channel.send(
            msg,
            reference=message,
            allowed_mentions=discord.AllowedMentions(roles=True),
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Detect repeated messages."""
        if self.guild is None:
            return

        channel = message.channel
        if not isinstance(message.author, discord.Member):
            return
        if message.author.bot:
            return
        if channel is None:
            return

        # Drop old messages
        now = int(time.time())
        cutoff = now - DURATION
        drop = [i for i in self.messages if i < cutoff]
        for ts in drop:
            del self.messages[ts]

        # Add the new message
        self.messages[now][message.author.id].append(message)

        # Count occurances.
        matching = sum(
            1
            for messages in self.messages.values()
            for prior in messages[message.author.id]
            if self.message_match(message, prior)
        )

        # Alert on spam.
        if matching >= REPEATED:
            self.prom_counter.inc()
            logging.info(
                "Spam detected. %s %s %s",
                message.author.name, message.channel.name,
                message.jump_url,
            )
            for messages in self.messages.values():
                messages.pop(message.author.id, None)
            await self.send_alert(message)
