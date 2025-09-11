"""Discord Cog to keep a message "pinned" at the end of a discussion."""

import logging

import discord
import pymongo.mongo_client
from discord.ext import commands

from cogs import base_cog

logger = logging.getLogger(__name__)


class PinnedMessage(base_cog.BaseCog):
    """Keep a message pinned to the end of a channel."""

    qualified_name = "Pinned Message"

    def __init__(
        self,
        bot: commands.Bot,
        messages: dict[int, str],
        **kwargs,
    ) -> None:
        super().__init__(bot=bot, **kwargs)
        self.bot = bot
        self.messages: dict[int, str] = messages
        self.last_message: dict[int, discord.Message] = {}
        self.mongo: pymongo.mongo_client.database.Collection | None
        if isinstance(self.mongodb, pymongo.mongo_client.database.Database):
            self.mongo = self.mongodb.get_collection("pinned_messages")
        else:
            self.mongo = None

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Popular prior messages from channel histories."""
        if self.bot.user:
            for channel_id, content in self.messages.items():
                message = await self.find_prior_message(channel_id, content)
                if message:
                    self.last_message[channel_id] = message

    async def find_prior_message(self, channel_id: int, content: str) -> None | discord.Message:
        """Return a prior message from a channel history."""
        assert self.bot.user is not None
        channel = self.bot.get_channel(channel_id)
        if isinstance(channel, discord.TextChannel):
            if self.mongo is not None:
                try:
                    got = self.mongo.find_one({"channel": channel_id})
                    if got is not None:
                        message_id = got["message"]
                        return await channel.get_partial_message(message_id).fetch()
                except Exception as e:  # pylint: disable=broad-exception-caught
                    logger.error("Failed to get message via MongoDB: %s", e)

            async for message in channel.history(limit=50, oldest_first=None):
                if message.author.id == self.bot.user.id and message.content == content:
                    return message
        return None

    async def bump_message(self, channel: discord.TextChannel) -> None:
        """Bump a pinned message in a channel."""
        if last := self.last_message.get(channel.id):
            await last.delete()

        msg = await channel.send(self.messages[channel.id], silent=True)
        if self.mongo is not None:
            try:
                self.mongo.replace_one(
                    {"channel": channel.id},
                    {"channel": channel.id, "message": msg.id},
                    True,
                )
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("Failed to save message to MongoDB: %s", e)

        self.last_message[channel.id] = msg

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Move message to the end of the channel."""
        if message.author.bot:
            return
        if not isinstance(message.channel, discord.TextChannel):
            return
        if message.channel.id not in self.messages:
            return
        await self.bump_message(message.channel)
