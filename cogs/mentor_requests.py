"""Discord module to publish mentor request queues."""
import asyncio
import logging
import re
import sqlite3
from typing import Sequence

import discord
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
        super().__init__(
            bot=bot,
            logger=logger,
            **kwargs,
        )
        self.conn = sqlite3.Connection(sqlite_db, isolation_level=None)
        self.exercism = exercism.AsyncExercism()
        self.channel_id = channel_id
        self.threads: dict[str, discord.Thread] = {}
        self.requests: dict[str, tuple[str, discord.Message]] = {}
        self.lock = asyncio.Lock()

        if tracks:
            self.tracks = tracks
        else:
            self.tracks = exercism.Exercism().all_tracks()
            self.tracks.sort()

    async def unarchive(self, thread: discord.Thread) -> None:
        """Ensure a thread is not archived."""
        if not thread.archived:
            return
        message = await thread.send("Sending a message to unarchive this thread.")
        await message.delete()

    async def update_mentor_requests(self):
        """Update threads with new/expires requests."""
        current_request_ids = set()
        for track in self.tracks:
            logging.debug("Updating mentor requests for track %s", track)
            thread = self.threads.get(track)
            if not thread:
                logger.warning("Failed to find track %s in threads", track)
                continue

            # Refresh the thread object.
            # This is helpful to update the is_archived bit.
            got = await thread.guild.fetch_channel(thread.id)
            assert isinstance(got, discord.Thread), f"Expected a Thread. {got=}"
            thread = got
            self.threads[track] = thread

            requests = await self.get_requests(track)
            current_request_ids.update(requests)
            logger.debug(f"Found {len(requests)} requests for {track}")

            for request_id, description in requests.items():
                if request_id in self.requests:
                    logger.debug(f"{request_id=} is already being tracked.")
                    continue
                logger.debug(f"Adding {request_id=}.")
                self.usage_stats[track] += 1
                async with self.lock:
                    message = await thread.send(description, suppress_embeds=True)
                    self.requests[request_id] = (track, message)
                    data = {
                        "request_id": request_id,
                        "track_slug": track,
                        "message_id": message.id,
                    }
                    self.conn.execute(QUERY["add_request"], data)
            await asyncio.sleep(2)

        drop = [
            (request_id, track, message)
            for request_id, (track, message) in list(self.requests.items())
            if request_id not in current_request_ids
        ]
        if drop:
            drops = "; ".join(
                f"{track}-{request_id}-{message.id}"
                for request_id, track, message in drop
            )
            logger.info("Dropping requests no longer in the queue: %s", drops)

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
                    await message.delete()
                except discord.errors.NotFound:
                    logger.info("Message not found; dropping from DB. %s", message.jump_url)
            await asyncio.sleep(0.1)

    @tasks.loop(minutes=10)
    async def task_update_mentor_requests(self):
        """Task loop to update mentor requests."""
        await self.update_mentor_requests()
        # Start up the task to delete old messages, if it is not yet running.
        # We only want to run that code after we've updated mentor requests once.
        if not self.task_delete_old_messages.is_running():  # pylint: disable=E1101
            self.task_delete_old_messages.start()  # pylint: disable=E1101

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Fetch tracks and configure threads as needed."""
        await self.load_data()
        if not self.task_update_mentor_requests.is_running():  # pylint: disable=E1101
            self.task_update_mentor_requests.start()  # pylint: disable=E1101

    @commands.is_owner()
    @commands.dm_only()
    @commands.command()
    async def requests_stats(self, ctx: commands.Context) -> None:
        """Command to dump stats."""
        msg = f"{len(self.requests)=}, {len(self.tracks)=}"
        await ctx.reply(msg)

    async def delete_old_messages(self) -> None:
        """Delete old request messages which do not have a corresponding request cached."""
        request_url_re = re.compile(r"\bhttps://exercism.org/mentoring/requests/(\w+)\b")
        request_ids = set(self.requests.keys())
        for track_slug, thread in self.threads.items():
            logging.debug("Deleting stale messages for track %s", track_slug)
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
                    if request_id not in request_ids:
                        logger.warning(
                            "Untracked request found! Deleting. %s %s",
                            track_slug,
                            request_id,
                        )
                        await message.delete()
                        self.conn.execute(QUERY["del_request"], {"request_id": request_id})
            await asyncio.sleep(1)

    @commands.is_owner()
    @commands.dm_only()
    @commands.command()
    async def requests_delete_old_messages(self, ctx: commands.Context) -> None:
        """Command to trigger delete_old_messages."""
        _ = ctx
        await self.delete_old_messages()

    @tasks.loop(hours=1)
    async def task_delete_old_messages(self):
        """Task to periodically run delete_old_messages."""
        await self.delete_old_messages()

    async def load_data(self) -> None:
        """Load Exercism data."""
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
        for request_id, track_slug, message_id in cur.fetchall():
            message = await self.threads[track_slug].fetch_message(message_id)
            assert message is not None, "Expected a message, got {message=}"
            self.requests[request_id] = (track_slug, message)

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
            track_title = req["track_title"]
            exercise_title = req["exercise_title"]
            student_handle = req["student_handle"]
            status = req["status"]
            url = req["url"]

            msg = f"{track_title.title()}: {url} => {exercise_title} "
            if status:
                msg += f"({student_handle}, {status})"
            else:
                msg += f"({student_handle})"

            requests[req["uuid"]] = msg
        return requests
