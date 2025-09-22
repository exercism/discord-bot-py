"""Discord Cog to detect spam."""

import collections
import logging
import time

import discord
import prometheus_client  # type: ignore
import tenacity
from discord.ext import commands

from cogs import base_cog

logger = logging.getLogger(__name__)

TITLE = "Spam Detector"
REPEATED = 5
DURATION = 10
DD = collections.defaultdict


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
        self.mod_channel_id = mod_channel
        self.prom_counter = prometheus_client.Counter(
            "spam_detected", "How many times spam was detected."
        )
        # timestamp, member id, messages
        self.messages: DD[int, DD[int, list[discord.Message]]] = DD(lambda: DD(list))
        self.mod_channel: discord.TextChannel | None = None
        self.mod_role_id: int | None = None

    @tenacity.retry(
        stop=tenacity.stop_after_attempt(4),
        wait=tenacity.wait_random_exponential(max=30),
    )
    def _load_data(self) -> None:
        """Load data with retries."""
        channel = self.bot.get_channel(self.mod_channel_id)
        assert isinstance(channel, discord.TextChannel), f"{channel} is not a TextChannel."
        self.mod_channel = channel

        guild = self.bot.get_guild(self.exercism_guild_id)
        assert guild is not None, "Could not find the guild."
        self.mod_role_id = [r.id for r in guild.roles if "moderator" in r.name][0]

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Fetch data when ready."""
        self._load_data()

    def message_match(self, one: discord.Message, two: discord.Message) -> bool:
        """Return if two messages match."""
        return (
            one.author == two.author
            and one.content == two.content
            and sorted(i.type for i in one.embeds) == sorted(i.type for i in two.embeds)
            and sorted(i.url for i in one.embeds if i.url) == sorted(
                i.url for i in two.embeds if i.url
            )
            and {hash(i) for i in one.attachments} == {hash(i) for i in two.attachments}
        )

    async def send_alert(self, message: discord.Message) -> None:
        """Send an alert about spam."""
        if not isinstance(message.channel, discord.TextChannel):
            return
        msg = f"<@&{self.mod_role_id}> Banning {message.author.name} for spam "
        msg += f"in {message.channel.name}. Same message {REPEATED} times.\n"
        msg += "**Content:**\n"
        msg += "\n".join("> " + m for m in message.content.splitlines())
        assert isinstance(self.mod_channel, discord.TextChannel)
        await self.mod_channel.send(msg)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Detect repeated messages."""
        if self.mod_channel is None:
            return

        channel = message.channel
        if not isinstance(message.author, discord.Member):
            return
        if message.author.bot:
            return
        if channel is None or not isinstance(channel, discord.TextChannel):
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
                message.author.name,
                channel.name,
                message.jump_url,
            )
            for messages in self.messages.values():
                if message.author.id and message.author.id in messages:
                    del messages[message.author.id]
            await self.send_alert(message)
            await message.author.ban(reason="Spam")
