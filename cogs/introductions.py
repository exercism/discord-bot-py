"""Discord Cog to ask people to introduce themself."""

import discord
import prometheus_client  # type: ignore
from discord.ext import commands

from cogs import base_cog


class IntroduceYourself(base_cog.BaseCog):
    """Respond to posts with introduction requests."""

    qualified_name = "Introduce yourself"

    def __init__(
        self,
        *,
        intro_channel: int,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.intro_channel = intro_channel
        self.prom_counter = prometheus_client.Counter(
            "intro_request", "How many times we asked people to post an intro"
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """React to one word introductions."""
        if (
            message.author.bot
            or message.channel is None
        ):
            return
        if not (
            isinstance(message.channel, discord.TextChannel)
            and message.channel.id == self.intro_channel
            and message.type == discord.MessageType.default
            and len(message.content.split()) == 1
        ):
            return

        thread = await message.create_thread(name=message.content)
        content = f"{message.author.mention} Hello! Welcome to Exercism! "
        content += "Would you like to please introduce yourself?"
        await thread.send(content=content, suppress_embeds=True)
