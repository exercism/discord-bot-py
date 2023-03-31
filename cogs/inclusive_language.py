#!/bin/python
"""Discord Cog to remind people to use inclusive language."""

import logging
import re
from typing import cast, Sequence

import discord
from discord.ext import commands


discord.utils.setup_logging()
logger = logging.getLogger(__name__)

MESSAGE = (
    "Hello 👋 This is a friendly (automated) request to not use gendered pronouns "
    'when greeting people. For example, rather than saying "hey guys" or "hey dudes", '
    'use something like "hey everyone", or "hey folks". '
    "At Exercism, we try to ensure that the community is actively welcoming to people of "
    "all backgrounds and genders, and this is a small thing that you can do to help."
    "\n\n"
    "You can learn more here: https://exercism.org/docs/community/being-a-good-community-member"
    "/the-words-that-we-use"
    "\n\n"
    "**Please consider editing your original message to make it more inclusive.**"
)
TITLE = "Inclusive Language Reminder!"


class InclusiveLanguage(commands.Cog):
    """Respond to posts with inclusivity reminders."""

    qualified_name = "Inclusive Language"

    def __init__(
        self,
        bot: commands.Bot,
        patterns: Sequence[re.Pattern],
        debug: bool,
        exercism_guild_id: int,
    ) -> None:
        self.bot = bot
        self.exercism_guild_id = exercism_guild_id
        self.patterns = patterns
        if debug:
            logger.setLevel(logging.DEBUG)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Add Emoji reactions on a new message."""
        channel = message.channel
        if channel is None:
            return
        if not any(pattern.search(message.content) for pattern in self.patterns):
            return
        if channel.type == discord.ChannelType.public_thread:
            await message.reply(MESSAGE, delete_after=60, suppress_embeds=True)
        elif channel.type == discord.ChannelType.text:
            typed_channel = cast(discord.TextChannel, channel)
            thread = await typed_channel.create_thread(
                name=TITLE, auto_archive_duration=60
            )
            content = f"{message.author.mention} {MESSAGE}\n\n{message.jump_url}"
            await thread.send(content=content, suppress_embeds=True)
