"""Sync streaming events from Exercism to Discord."""
import asyncio
import logging
import sqlite3
from typing import Any

import discord
import discord.utils
import requests  # type: ignore
from discord.ext import commands
from discord.ext import tasks

from cogs import base_cog
from exercism_lib import exercism

QUERY = {
    "add_event": "INSERT INTO streaming_events VALUES (:discord_id, :exercism_id)",
    "del_event": "DELETE FROM streaming_events WHERE exercism_id = :exercism_id",
    "get_events": "SELECT discord_id, exercism_id FROM streaming_events",
}

MAPPING = {
    "name": "title",
    "description": "description",
    "start_time": "starts_at",
    "end_time": "ends_at",
}

ATTR_MAPPING = {
    "description": "description",
    "start_time": "start_time",
    "end_time": "end_time",
    "location": "location",
    "name": "name",
}

logger = logging.getLogger(__name__)


class StreamingEvents(base_cog.BaseCog):
    """Sync events."""

    qualified_name = "Sync Streaming Events"

    def __init__(
        self,
        sqlite_db: str,
        default_location_url: str,
        **kwargs,
    ) -> None:
        super().__init__(
            logger=logger,
            **kwargs,
        )
        self.exercism = exercism.AsyncExercism()
        self.default_location_url = default_location_url
        self.conn = sqlite3.Connection(sqlite_db, isolation_level=None)
        self.tracked_events: dict[int, discord.ScheduledEvent] = {}

    def add_thumbnail(self, exercism_event: dict[str, Any], data: dict[str, str | bytes]) -> None:
        """Add a thumbnail to the data dict."""
        if exercism_event.get("thumbnail_url"):
            resp = requests.get(exercism_event["thumbnail_url"], timeout=5)
            if resp.ok:
                try:
                    discord.utils._get_mime_type_for_image(resp.content)  # pylint: disable=W0212
                except ValueError:
                    logger.warning(
                        "Event %d has an invalid thumbnail url: %s",
                        exercism_event["id"],
                        exercism_event["thumbnail_url"],
                    )
                else:
                    data["image"] = resp.content

    async def add_exercism_event(
        self,
        exercism_event: dict[str, Any],
        data: dict[str, str | bytes],
        guild: discord.Guild,
    ) -> None:
        """Add a new ScheduledEvent to Discord."""
        title = exercism_event["title"]
        exercism_id = exercism_event["id"]

        self.add_thumbnail(exercism_event, data)
        logging.info("Creating new event, %d, %s", exercism_id, title)
        discord_event = await guild.create_scheduled_event(**data)  # type: ignore
        self.tracked_events[exercism_id] = discord_event
        logging.info("Created new event, %d, %d", exercism_id, discord_event.id)
        self.conn.execute(
            QUERY["add_event"],
            {"discord_id": discord_event.id, "exercism_id": exercism_id},
        )

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
        exercism_events = await self.exercism.future_streaming_events()
        if not exercism_events:
            return

        # Add/update Discord Guild Events.
        for exercism_event in exercism_events:
            data = {
                discord_key: exercism_event[event_key]
                for discord_key, event_key in MAPPING.items()
            }
            for key, value in data.items():
                if isinstance(value, str):
                    data[key] = value.strip()
            data.update({
                "privacy_level": discord.PrivacyLevel.guild_only,
                "entity_type": discord.EntityType.external,
            })
            links = exercism_event.get("links", {})
            data["location"] = links.get("watch", None) or self.default_location_url
            exercism_id = exercism_event["id"]

            if exercism_id not in self.tracked_events:
                await self.add_exercism_event(exercism_event, data, guild)
                await asyncio.sleep(5)
            else:
                discord_event = self.tracked_events[exercism_id]
                differs = {
                    data_key: (data[data_key], getattr(discord_event, attr_key))
                    for data_key, attr_key in ATTR_MAPPING.items()
                    if data[data_key] != getattr(discord_event, attr_key)
                }
                if differs:
                    logging.info(
                        "Updating event, %d, %s; changed: %r",
                        discord_event.id,
                        exercism_event["title"],
                        differs,
                    )
                    self.add_thumbnail(exercism_event, data)
                    await discord_event.edit(**data)
                    await asyncio.sleep(5)

        # Delete Events from Discord if they are no longer on Exercism.
        event_ids = {exercism_event["id"] for exercism_event in exercism_events}
        for event_id in list(self.tracked_events):
            if event_id in event_ids:
                continue
            logging.info("Drop deleted event, %d, %d", event_id, self.tracked_events[event_id].id)
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

        tracked_events = {}
        for discord_id, exercism_id in cur.fetchall():
            if discord_id in guild_events:
                tracked_events[exercism_id] = guild_events[discord_id]
            else:
                logger.warning(
                    "Event is no longer in Discord. Drop from DB. (%s, %s)",
                    discord_id, exercism_id
                )
                self.conn.execute(QUERY["del_event"], {"exercism_id": exercism_id})

        self.tracked_events = tracked_events
        self.sync_events.start()  # pylint: disable=E1101

    def details(self) -> str:
        """Return cog details."""
        data = [
            (exercism_id, event.id, event.name)
            for exercism_id, event in self.tracked_events.items()
        ]
        return str(data)
