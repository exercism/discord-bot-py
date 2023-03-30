"""Sync streaming events from Exercism to Discord."""
import asyncio
import logging

import discord
import requests  # type: ignore
from discord.ext import commands
from discord.ext import tasks
from exercism_lib import exercism


discord.utils.setup_logging()
logger = logging.getLogger(__name__)


class StreamingEvents(commands.Cog):
    """Sync events."""

    qualified_name = "Sync Streaming Events"

    def __init__(
        self,
        bot: commands.Bot,
        debug: bool,
        exercism_guild_id: int,
        default_location_url: str
    ) -> None:
        self.bot = bot
        self.exercism = exercism.Exercism()
        self.exercism_guild_id = exercism_guild_id
        self.default_location_url = default_location_url
        if debug:
            logger.setLevel(logging.DEBUG)
        self.sync_events.start()  # pylint: disable=E1101

    @tasks.loop(minutes=60)
    async def sync_events(self):
        """Sync Events."""
        guild = self.bot.get_guild(self.exercism_guild_id)
        if guild is None:
            logger.error("Failed to retrieve the guild.")
            return
        if not guild.me.guild_permissions.manage_events:
            logger.error("No permission to manage events.")
            return

        exercism_events = self.exercism.future_streaming_events()
        discord_events = guild.scheduled_events
        discord_keyed = {(i.name, i.start_time): i for i in discord_events}

        mapping = {
            "name": "title",
            "description": "description",
            "start_time": "starts_at",
            "end_time": "ends_at",
        }
        attr_mapping = {
            "description": "description",
            "start_time": "start_time",
            "end_time": "end_time",
            "location": "location",
        }
        for event in exercism_events:
            data = {
                discord_key: event[event_key]
                for discord_key, event_key in mapping.items()
            }
            data.update({
                "privacy_level": discord.PrivacyLevel.guild_only,
                "entity_type": discord.EntityType.external,
            })
            links = event.get("links", {})
            data["location"] = links.get("watch", None) or self.default_location_url
            if event.get("thumbnail_url"):
                resp = requests.get(event["thumbnail_url"], timeout=5)
                if resp.ok:
                    data["image"] = resp.content

            key = (event["title"], event["starts_at"])
            if key not in discord_keyed:
                logging.info("Created new event, %s", event["title"])
                await guild.create_scheduled_event(**data)
                await asyncio.sleep(5)
            else:
                discord_event = discord_keyed[key]
                if any(
                    data[data_key] != getattr(discord_event, attr_key)
                    for data_key, attr_key in attr_mapping.items()
                ):
                    logging.info("Updating event, %s", event["title"])
                    await discord_event.edit(**data)
                    await asyncio.sleep(5)

    @sync_events.before_loop
    async def before_sync_events(self):
        """Wait until ready prior to starting the event loop."""
        await self.bot.wait_until_ready()
