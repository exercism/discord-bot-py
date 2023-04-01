"""Sync streaming events from Exercism to Discord."""
import asyncio
import logging
import sqlite3
from typing import Any

import discord
import requests  # type: ignore
from discord.ext import commands
from discord.ext import tasks
from exercism_lib import exercism

QUERY = {
    "add_event": "INSERT INTO streaming_events VALUES (:discord_id, :exercism_id)",
    "del_event": "DELETE FROM streaming_events WHERE exercism_id = :exercism_id",
    "get_events": "SELECT discord_id, exercism_id FROM streaming_events",
}

logger = logging.getLogger(__name__)


class StreamingEvents(commands.Cog):
    """Sync events."""

    qualified_name = "Sync Streaming Events"

    def __init__(
        self,
        bot: commands.Bot,
        debug: bool,
        exercism_guild_id: int,
        sqlite_db: str,
        default_location_url: str
    ) -> None:
        self.bot = bot
        self.exercism = exercism.Exercism()
        self.exercism_guild_id = exercism_guild_id
        self.default_location_url = default_location_url
        self.conn = sqlite3.Connection(sqlite_db, isolation_level=None)
        self.tracked_events: dict[int, discord.ScheduledEvent] = {}
        if debug:
            logger.setLevel(logging.DEBUG)

    def add_thumbnail(self, exercism_event: dict[str, Any], data: dict[str, str | bytes]) -> None:
        """Add a thumbnail to the data dict."""
        if exercism_event.get("thumbnail_url"):
            resp = requests.get(exercism_event["thumbnail_url"], timeout=5)
            if resp.ok:
                data["image"] = resp.content

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
        if not exercism_events:
            return

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
            "name": "name",
        }
        # Add/update Discord Guild Events.
        for exercism_event in exercism_events:
            data = {
                discord_key: exercism_event[event_key]
                for discord_key, event_key in mapping.items()
            }
            data.update({
                "privacy_level": discord.PrivacyLevel.guild_only,
                "entity_type": discord.EntityType.external,
            })
            links = exercism_event.get("links", {})
            data["location"] = links.get("watch", None) or self.default_location_url
            title = exercism_event["title"]
            exercism_id = exercism_event["id"]

            if exercism_id not in self.tracked_events:
                self.add_thumbnail(exercism_event, data)
                logging.info("Created new event, %s", title)
                discord_event = await guild.create_scheduled_event(**data)
                self.tracked_events[exercism_id] = discord_event
                self.conn.execute(
                    QUERY["add_event"],
                    {"discord_id": discord_event.id, "exercism_id": exercism_id},
                )
                await asyncio.sleep(5)
            else:
                discord_event = self.tracked_events[exercism_id]
                if any(
                    data[data_key] != getattr(discord_event, attr_key)
                    for data_key, attr_key in attr_mapping.items()
                ):
                    self.add_thumbnail(exercism_event, data)
                    logging.info("Updating event, %s", title)
                    await discord_event.edit(**data)
                    await asyncio.sleep(5)

        # Delete Events from Discord if they are no longer on Exercism.
        event_ids = {exercism_event["id"] for exercism_event in exercism_events}
        for event_id in list(self.tracked_events):
            if event_id in event_ids:
                continue
            logging.info("Drop deleted event, %d", event_id)
            self.conn.execute(QUERY["del_event"], {"exercism_id": event_id})
            await self.tracked_events[event_id].delete()
            del self.tracked_events[event_id]

    @commands.Cog.listener()
    async def on_ready(self):
        """Load Discord.ScheduledEvents data on ready."""
        guild = self.bot.get_guild(self.exercism_guild_id)
        if guild is None:
            logger.error("Failed to retrieve the guild.")
            return
        if not guild.me.guild_permissions.manage_events:
            logger.error("No permission to manage events.")
            return

        # Load events from Discord and the DB.
        guild_events = {guild_event.id: guild_event for guild_event in guild.scheduled_events}
        cur = self.conn.execute(QUERY["get_events"])
        self.tracked_events = {
            exercism_id: guild_events[discord_id]
            for discord_id, exercism_id in cur.fetchall()
        }

        self.sync_events.start()  # pylint: disable=E1101
