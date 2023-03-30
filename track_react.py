#!/bin/python

import asyncio
import logging
import re

import discord
from discord.ext import commands


discord.utils.setup_logging()
logger = logging.getLogger(__name__)


class TrackReact(commands.Cog):
    """Respond to support posts with a track reactions."""

    qualified_name = "Track React"

    def __init__(
        self,
        bot: commands.Bot,
        aliases: dict[str, str],
        case_sensitive: set[str],
        debug: bool,
    ) -> None:
        self.bot = bot
        self.reacts: dict[re.Pattern, discord.Emoji] = {}
        self.messages: dict[int, discord.Message] = {}
        self.aliases = aliases
        self.case_sensitive = case_sensitive
        if debug:
            logger.setLevel(logging.DEBUG)

    @commands.Cog.listener()
    async def on_ready(self):
        guild = self.bot.get_guild(self.bot.exercism_guild_id)
        emojis = await guild.fetch_emojis()
        tracks = {
            e.name.removeprefix("track_"): e
            for e in emojis
            if e.name.startswith("track_")
        }
        for alias, src in self.aliases.items():
            if src not in tracks:
                logger.warning(f"Could not find track {src}")
            else:
                tracks[alias] = tracks[src]

        re_reacts = {}
        for track, emoji in tracks.items():
            # Case sensitive for single char tracks and a whitelist.
            flags = re.IGNORECASE
            if len(track) == 1 or track in self.case_sensitive:
                track = track.title()
                flags = 0

            # Mutli-word tracks: convert _ to .?
            track = track.replace("_", ".?")

            compiled = re.compile(r"\b" + track + r"\b", flags)
            re_reacts[compiled] = emoji
        self.reacts = re_reacts

        logger.debug(self.reacts)

    @staticmethod
    def parse_codeblocks(message: str) -> str:
        lines = []
        in_block = False
        for line in message.splitlines():
            if line.startswith("```"):
                if not in_block:
                    parts = line.split()
                    if len(parts) == 1:
                        lines.append(parts[0].title())
                in_block = not in_block
            if not in_block:
                lines.append(line)
        return "\n".join(lines)

    async def add_reacts(self, message, content):
        if not message.guild:
            return
        if not message.channel.permissions_for(message.guild.me).add_reactions:
            logger.warning(
                "Missing add_reactions permission for "
                f"{message.channel.name} in {message.guild.name}"
            )
            return
        content = self.parse_codeblocks(content)
        re_reacts = self.reacts
        reactions = set()
        for compiled, reaction in re_reacts.items():
            if compiled.search(content):
                reactions.add(reaction)
        for reaction in reactions:
            # logger.warning(f"Reacting with {reaction}")
            await message.add_reaction(reaction)

    @commands.Cog.listener()
    async def on_thread_create(self, thread):
        await asyncio.sleep(0.5)

        if thread.id not in self.messages:
            logger.warning(f"Could not find message for thread {thread.id}")
            return
        message = self.messages.pop(thread.id)
        await self.add_reacts(message, message.channel.name)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.channel.type == discord.ChannelType.public_thread:
            self.messages[message.channel.id] = message
        await self.add_reacts(message, message.content)
