"""Provide app commands to post canned mod messages."""

import logging
import typing

import discord
from discord import app_commands
from discord.ext import commands

from cogs import base_cog

logger = logging.getLogger(__name__)


class ModMessage(base_cog.BaseCog):
    """Provide canned bot messages."""

    qualified_name = "Mod Message"

    def __init__(
        self,
        bot: commands.Bot,
        canned_messages: dict[str, str],
        exercism_guild_id: int,
        **kwargs,
    ) -> None:
        super().__init__(
            bot=bot,
            exercism_guild_id=exercism_guild_id,
            **kwargs,
        )
        self.canned_messages = canned_messages
        self.exercism_guild_id = exercism_guild_id
        bot.tree.add_command(self.make_command(), guild=discord.Object(self.exercism_guild_id))

    def make_command(self) -> app_commands.Command:
        """Return an app command with a dynamic list of message types."""

        @app_commands.command(name="mod_message")  # type: ignore
        @commands.guild_only()
        @commands.has_role("moderators")
        @commands.bot_has_permissions(send_messages=True)
        @app_commands.choices(
            message=[
                app_commands.Choice(name=name, value=name)
                for name in self.canned_messages
            ]
        )
        async def mod_message(
            interaction: discord.Interaction,
            message: app_commands.Choice[str],
            mention: typing.Optional[discord.Member],
        ) -> None:
            """App command to post a mod message via the bot."""
            channel = interaction.channel
            if not isinstance(channel, discord.abc.Messageable):
                logger.debug("Interaction is not in a messageable channel.")
                return

            member = interaction.user
            if not isinstance(member, discord.Member):
                logger.debug("Interaction user is not a guild member.")
                return

            guild = channel.guild
            if not isinstance(guild, discord.Guild):
                logger.debug("Interaction channel is not in a guild.")
                return

            if "moderators" not in {r.name for r in member.roles}:
                await interaction.response.send_message(
                    "That command is only for moderators; sorry!",
                    ephemeral=True,
                )
                logger.debug("Interaction member is not a moderator.")
                return

            if message.value not in self.canned_messages:
                await interaction.response.send_message(
                    "That canned message was not found! This is a bug.",
                    ephemeral=True
                )
                logger.warning("Message type %s not valid.", message.value)
                return

            permissions = channel.permissions_for(guild.me)
            if not permissions.send_messages:
                await interaction.response.send_message(
                    "I do not have permissions to send messages in this channel.",
                    ephemeral=True,
                    delete_after=30,
                )
                logger.warning("No permission to post in %s (%d)", channel, channel.id)
                return

            extra = {"tags": {"message": message.value, "sender": member.display_name}}
            logger.info("Sending canned message.", extra=extra)
            await interaction.response.send_message(
                "Sending canned message.",
                ephemeral=True,
                delete_after=5,
            )
            content = self.canned_messages[message.value]
            if mention:
                content = f"{mention.mention} {content}"
            self.usage_stats[message.value] += 1
            await channel.send(content, suppress_embeds=True)

        return mod_message

    @commands.is_owner()
    @commands.dm_only()
    @commands.command()
    async def sync_mod_message(self, ctx: commands.Context) -> None:
        """Sync app commands to the Guild."""
        _ = ctx
        logger.info("Syncing ModMessage.")
        await self.bot.tree.sync(guild=discord.Object(self.exercism_guild_id))
