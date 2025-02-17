"""Discord module to publish mentor request queues."""
import asyncio
import logging
import re
import sqlite3
from typing import Sequence

import discord
import prometheus_client  # type: ignore
from discord.ext import commands
from discord.ext import tasks
from exercism_lib import exercism

from cogs import base_cog

logger = logging.getLogger(__name__)

QUERY = {
    "add_request": "INSERT INTO requests VALUES (:request_id, :track_slug, :message_id)",
    "del_request": "DELETE FROM requests WHERE request_id = :request_id",
    "get_requests": "SELECT request_id, track_slug, message_id FROM requests",
    "get_theads": "SELECT track_slug, message_id FROM track_threads",
    "add_thead": "INSERT INTO track_threads VALUES (:track_slug, :message_id)",
}
PROM_TRACK_COUNT = prometheus_client.Gauge("mentor_requests_tracks", "Number of tracks")
ACTIVE_REQUESTS = prometheus_client.Gauge("mentor_requests", "Number of requests")
REQUEST_QUEUED = prometheus_client.Counter(
    "mentor_request_queued", "Number of requests queued", ["track"],
)
PROM_UPDATE_HIST = prometheus_client.Histogram("mentor_requests_update", "Update requests")
PROM_UPDATE_TRACK_HIST = prometheus_client.Histogram(
    "mentor_requests_update_track", "Update one track", ["track"],
)
PROM_LAST_UPDATE = prometheus_client.Gauge(
    "mentor_requests_last_update", "Timestamp of last update",
)


class RequestNotifier(base_cog.BaseCog):
    """Update Discord with Mentor Requests."""

    qualified_name = "Request Notifier"

    def __init__(
        self,
        bot: commands.Bot,
        channel_id: int,
        sqlite_db: str,
        tracks: Sequence[str] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(bot=bot, **kwargs)
        self.conn = sqlite3.Connection(sqlite_db, isolation_level=None)
        self.exercism = exercism.AsyncExercism()
        self.channel_id = channel_id
        self.threads: dict[str, discord.Thread] = {}
        self.requests: dict[str, tuple[str, discord.Message]] = {}
        self.lock = asyncio.Lock()

        if tracks:
            self.tracks = list(tracks)
        else:
            self.tracks = exercism.Exercism().all_tracks()
        self.tracks.sort()
        PROM_TRACK_COUNT.set(len(self.tracks))
        PROM_LAST_UPDATE.set_to_current_time()

        self.synced_tracks: set[str] = set()
        self.task_update_mentor_requests.start()  # pylint: disable=E1101
        self.task_delete_old_messages.start()  # pylint: disable=E1101

    async def unarchive(self, thread: discord.Thread) -> None:
        """Ensure a thread is not archived."""
        if not thread.archived:
            return
        async with asyncio.timeout(10):
            message = await thread.send("Sending a message to unarchive this thread.")
        async with asyncio.timeout(10):
            await message.delete()

    async def update_track_requests(self, track: str) -> dict[str, str]:
        """Update mentor requests for one track, returning current requests."""
        logger.debug("Updating mentor requests for track %s", track)
        thread = self.threads.get(track)
        if not thread:
            logger.warning("Failed to find track %s in threads", track)
            return {}

        # Refresh the thread object.
        # This is helpful to update the is_archived bit.
        try:
            async with asyncio.timeout(10):
                got = await thread.guild.fetch_channel(thread.id)
        except asyncio.TimeoutError:
            logger.warning("fetch_channel timed out for track %s (%s).", track, thread.id)
            return {}
        assert isinstance(got, discord.Thread), f"Expected a Thread. {got=}"
        thread = got
        self.threads[track] = thread

        async with asyncio.timeout(15):
            requests = await self.get_requests(track)
        logger.debug("Found %d requests for %s.", len(requests), track)

        REQUEST_QUEUED.labels(track).inc(len(set(requests) - set(self.requests)))
        for request_id, description in requests.items():
            if request_id in self.requests:
                logger.debug("Request %s-%s is already being tracked.", track, request_id)
                continue
            logger.debug("Adding request %s in %s.", request_id, track)
            self.usage_stats[track] += 1
            async with self.lock:
                async with asyncio.timeout(10):
                    message = await thread.send(description, suppress_embeds=True)
                self.requests[request_id] = (track, message)
                data = {
                    "request_id": request_id,
                    "track_slug": track,
                    "message_id": message.id,
                }
                self.conn.execute(QUERY["add_request"], data)
            # Update the gauge which shows the last success timestamp.
            PROM_LAST_UPDATE.set_to_current_time()
        return requests

    @PROM_UPDATE_HIST.time()
    async def update_mentor_requests(self) -> None:
        """Update threads with new/expires requests."""
        logger.debug("Start update_mentor_requests()")

        drop: list[tuple[str, str, discord.Message]] = []
        synced_tracks: set[str] = set()
        for track in self.tracks:
            try:
                async with asyncio.timeout(30):
                    with PROM_UPDATE_TRACK_HIST.labels(track).time():
                        requests = await self.update_track_requests(track)
                    synced_tracks.add(track)
            except asyncio.TimeoutError:
                logger.warning("update_track_requests timed out for track %s.", track)
            else:
                expired = [
                    (request_id, track, message)
                    for request_id, (request_track, message) in self.requests.items()
                    if request_track == track and request_id not in requests
                ]
                drop.extend(expired)
                expired_fmt = "; ".join(
                    f"{request_id}-{message.id}"
                    for request_id, track, message in expired
                )
                logger.debug("Expired requests for %s: %s", track, expired_fmt)
            await asyncio.sleep(1)
        self.synced_tracks = synced_tracks

        if len(drop) > 25:
            logger.info("Found %d requests to drop. Truncating to 25.", len(drop))
            drop = drop[:25]

        if drop:
            drops = "; ".join(
                f"{track}-{request_id}-{message.id}"
                for request_id, track, message in drop
            )
            logger.debug("Dropping requests no longer in the queue: %s", drops)

        for request_id, track, message in drop:
            async with self.lock:
                self.conn.execute(QUERY["del_request"], {"request_id": request_id})
                del self.requests[request_id]
        await asyncio.sleep(0.1)

        for request_id, track, message in drop:
            assert track in self.threads, f"Could not find {track=} in threads."
            await self.unarchive(self.threads[track])
            async with self.lock:
                try:
                    async with asyncio.timeout(10):
                        await message.delete()
                except discord.errors.NotFound:
                    logger.info("Message not found; dropping from DB. %s", message.jump_url)
            await asyncio.sleep(0.1)
        ACTIVE_REQUESTS.set(len(self.requests))
        logger.debug("End update_mentor_requests()")

    @tasks.loop(minutes=10)
    async def task_update_mentor_requests(self):
        """Task loop to update mentor requests."""
        try:
            async with asyncio.timeout(60 * 10):
                await self.update_mentor_requests()
        except asyncio.TimeoutError:
            logger.warning("update_mentor_requests timed out after 10 minutes.")
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception("Unhandled exception using update_mentor_requests.")

    @task_update_mentor_requests.before_loop
    async def before_update_mentor_requests(self):
        """Before starting the update_mentor_requests task, wait for ready and load data."""
        await self.bot.wait_until_ready()
        await self.load_data()

    @tasks.loop(hours=1)
    async def task_delete_old_messages(self):
        """Task to periodically run delete_old_messages."""
        await self.delete_old_messages()

    @task_delete_old_messages.before_loop
    async def before_delete_old_messages(self):
        """Before starting the update_mentor_requests task."""
        await self.bot.wait_until_ready()

    @commands.is_owner()
    @commands.dm_only()
    @commands.command()
    async def requests_stats(self, ctx: commands.Context) -> None:
        """Command to dump stats."""
        msg = f"{len(self.requests)=}, {len(self.tracks)=}"
        await ctx.reply(msg)

    async def delete_old_messages(self) -> None:
        """Delete old request messages which do not have a corresponding request cached."""
        logger.debug("Start delete_old_messages()")
        request_url_re = re.compile(r"\bhttps://exercism.org/mentoring/requests/(\w+)\b")
        request_ids = set(self.requests.keys())
        for track_slug in self.synced_tracks:
            thread = self.threads.get(track_slug)
            if not thread:
                logger.warning("delete_old_messages does not have a thread for %s.", track_slug)
                continue
            logger.debug("Deleting stale messages for track %s", track_slug)
            await self.unarchive(thread)
            async with self.lock:
                async for message in thread.history():
                    if message.author != thread.owner:
                        continue
                    if message == thread.starter_message:
                        continue
                    match = request_url_re.search(message.content)
                    if match is None:
                        continue
                    request_id = match.group(1)
                    if request_id not in request_ids or self.requests[request_id][1] != message:
                        logger.debug(
                            "Untracked request found! Deleting. %s %s",
                            track_slug,
                            request_id,
                        )
                        await message.delete()
                        self.conn.execute(QUERY["del_request"], {"request_id": request_id})
                        await asyncio.sleep(0.5)
            await asyncio.sleep(1)
        logger.debug("End delete_old_messages()")

    @commands.is_owner()
    @commands.dm_only()
    @commands.command()
    async def requests_delete_old_messages(self, ctx: commands.Context) -> None:
        """Command to trigger delete_old_messages."""
        _ = ctx
        await self.delete_old_messages()

    async def load_data(self) -> None:
        """Load Exercism data."""
        logger.debug("Starting load_data()")
        guild = self.bot.get_guild(self.exercism_guild_id)
        assert guild is not None, "Could not find the guild."

        cur = self.conn.execute(QUERY["get_theads"])
        self.threads = {}
        for track_slug, message_id in cur.fetchall():
            thread = await guild.fetch_channel(message_id)
            if thread is None:
                raise RuntimeError(f"Unable to find thread {message_id} for track {track_slug}")
            assert isinstance(thread, discord.Thread), f"{thread=} is not a Thread."
            self.threads[track_slug] = thread

        channel = guild.get_channel(self.channel_id)
        assert isinstance(channel, discord.TextChannel), f"{channel} is not a TextChannel."
        for track in self.tracks:
            if track in self.threads:
                continue
            thread = await channel.create_thread(
                name=track.title(),
                type=discord.ChannelType.public_thread,
            )
            self.conn.execute(
                QUERY["add_thead"],
                {"track_slug": track, "message_id": thread.id},
            )
            self.threads[track] = thread
            await asyncio.sleep(5)

        cur = self.conn.execute(QUERY["get_requests"])
        self.requests = {}
        db_requests = list(cur.fetchall())
        track_slugs = {track_slug for _, track_slug, _ in db_requests}
        for track_slug in track_slugs:
            messages = {}
            try:
                async with asyncio.timeout(8):
                    async for message in self.threads[track_slug].history(limit=200):
                        messages[message.id] = message
            except asyncio.TimeoutError:
                logger.warning("load_data thread history(%s): TimeoutError!", track_slug)
            logger.debug("Loaded %d messages from %s thread.", len(messages), track_slug)

            for request_id, request_track_slug, message_id in db_requests:
                if request_track_slug != track_slug:
                    continue
                request_message = messages.get(int(message_id))
                if request_message is None:
                    logger.warning(
                        "load_data Could not find message %s in %s; DELETE from DB.",
                        message_id,
                        track_slug,
                    )
                    self.conn.execute(QUERY["del_request"], {"request_id": request_id})
                else:
                    self.requests[request_id] = (track_slug, request_message)
        logger.debug("End load_data().")

    @commands.is_owner()
    @commands.dm_only()
    @commands.command()
    async def requests_reload(self, ctx: commands.Context) -> None:
        """Command to reload data."""
        _ = ctx  # unused
        await self.load_data()

    async def get_requests(self, track_slug: str) -> dict[str, str]:
        """Return formatted mentor requests."""
        requests = {}
        for req in await self.exercism.mentor_requests(track_slug):
            # uuid = req["uuid"]
            track_title = req["track"]["title"]
            exercise_title = req["exercise"]["title"]
            student_handle = req["student"]["handle"]
            status = req["status"]
            url = req["url"]

            msg = f"{track_title.title()}: {url} => {exercise_title} "
            if status:
                msg += f"({student_handle}, {status})"
            else:
                msg += f"({student_handle})"

            requests[req["uuid"]] = msg
        return requests
