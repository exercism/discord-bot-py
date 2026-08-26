"""Discord Cog to detect spam."""

import collections
import datetime
import logging
import time

import discord
import prometheus_client  # type: ignore
import tenacity
from discord.ext import commands

from cogs import base_cog

logger = logging.getLogger(__name__)

TITLE = "Spam Detector"
# Message count and window (seconds)
TRIGGER_COUNT_DURATIONS = [(5, 40), (3, 20), (2, 10)]
MAX_DURATION = max(i[1] for i in TRIGGER_COUNT_DURATIONS)
DD = collections.defaultdict

PROM_SPAM_DETECTED = prometheus_client.Counter("spam_detected", "How many times spam was detected.")
PROM_MSG_COUNT = prometheus_client.Gauge("spam_msg_counter", "Messages per user", ["user"])
PROM_MSG_REPEATS = prometheus_client.Gauge(
    "spam_repeated_msg", "Number of times a user repeated something", ["user"]
)


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
        # timestamp, member id, messages
        self.messages: DD[int, DD[int, list[discord.Message]]] = DD(lambda: DD(list))
        self.mod_channel: discord.TextChannel | None = None

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

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Fetch data when ready."""
        self._load_data()

    def message_match(self, one: discord.Message, two: discord.Message) -> bool:
        """Return if two messages match."""
        return (one.author == two.author and one.content == two.content)

    async def send_alert(self, message: discord.Message) -> None:
        """Send an alert about spam."""
        if not isinstance(message.channel, discord.TextChannel):
            return
        msg = f"Banning {message.author.name} for spam "
        msg += f"in {message.channel.name}. Same message multiple times in short period.\n"
        assert isinstance(self.mod_channel, discord.TextChannel)
        post = await self.mod_channel.send(msg)
        if message.content:
            thread = await post.create_thread(name="Banned post", auto_archive_duration=1440)
            await thread.send(content=message.content, embeds=message.embeds)
        else:
            logging.info(
                "Spam message did not have any content. %d attachments, %d embeds, %r",
                len(message.attachments),
                len(message.embeds),
                message,
            )

    def count_matching_messages(self, message: discord.Message, since: int) -> int:
        """Return how many prior messages match since N timestamp."""
        return sum(
            1
            for ts, messages in self.messages.items()
            if ts >= since
            for prior in messages[message.author.id]
            if self.message_match(message, prior)
        )

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
        if channel is None or not isinstance(channel, (discord.TextChannel, discord.Thread)):
            return

        # Drop old messages
        now = int(time.time())
        cutoff = now - MAX_DURATION
        drop = [i for i in self.messages if i < cutoff]
        for ts in drop:
            del self.messages[ts]

        # Add the new message
        self.messages[now][message.author.id].append(message)

        # Write metrics
        repeats = collections.defaultdict[str, int](int)
        total = 0
        for ts, messages in self.messages.items():
            if ts >= cutoff:
                total += len(messages[message.author.id])
                for msg in messages[message.author.id]:
                    repeats[msg.content] += 1

        name = message.author.global_name or message.author.name
        PROM_MSG_COUNT.labels(name).set(total)
        PROM_MSG_REPEATS.labels(name).set(max(repeats.values()))

        # Check if the message triggers the filter.
        if any(
            self.count_matching_messages(message, now - duration) > count
            for count, duration in TRIGGER_COUNT_DURATIONS
        ):
            PROM_SPAM_DETECTED.inc()
            logging.info(
                "Spam detected. %s %s %s",
                message.author.name,
                channel.name,
                message.content,
            )
            for messages in self.messages.values():
                if message.author.id and message.author.id in messages:
                    del messages[message.author.id]
            # Ban, send a mod channel message, and clean up anything that may have slipped through.
            await message.author.ban(reason="Spam")
            logging.info("Banned user %s", message.author.name)
            after = datetime.datetime.now() - datetime.timedelta(seconds=5 * 60)
            async for m in message.author.history(limit=10, after=after):
                await m.delete()
            logging.info("Removed any messages from spammer %s", message.author.name)
            await self.send_alert(message)
            logging.info("Sent a mod message about %s", message.author.name)
