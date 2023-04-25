"""Discord module to publish mentor request queues."""
import asyncio
import logging
import sqlite3
from typing import Sequence

import discord
from discord.ext import commands
from discord.ext import tasks
from exercism_lib import exercism


logger = logging.getLogger(__name__)

QUERY = {
    "add_request": "INSERT INTO requests VALUES (:request_id, :track_slug, :message_id)",
    "del_request": "DELETE FROM requests WHERE request_id = :request_id",
    "get_requests": "SELECT request_id, track_slug, message_id FROM requests",
    "get_theads": "SELECT track_slug, message_id FROM track_threads",
    "add_thead": "INSERT INTO track_threads VALUES (:track_slug, :message_id)",
}


class RequestNotifier(commands.Cog):
    """Update Discord with Mentor Requests."""

    qualified_name = "Request Notifier"

    def __init__(
        self,
        bot: commands.Bot,
        channel_id: int,
        debug: bool,
        exercism_guild_id: int,
        sqlite_db: str,
        tracks: Sequence[str] | None = None,
    ) -> None:
        self.bot = bot
        self.conn = sqlite3.Connection(sqlite_db, isolation_level=None)
        self.exercism = exercism.AsyncExercism()
        self.channel_id = channel_id
        self.tracks = list(tracks or [])
        self.threads: dict[str, discord.Thread] = {}
        self.requests: dict[str, tuple[str, discord.Message]] = {}
        self.exercism_guild_id = exercism_guild_id
        if debug:
            logger.setLevel(logging.DEBUG)

    @tasks.loop(minutes=5)
    async def update_mentor_requests(self):
        """Update threads with new/expires requests."""
        current_request_ids = set()
        for track in self.tracks:
            thread = self.threads.get(track)
            if not thread:
                logger.warning("Failed to find track %s in threads", track)
                continue

            requests = await self.get_requests(track)
            current_request_ids.update(requests)

            for request_id, description in requests.items():
                if request_id in self.requests:
                    continue
                message = await thread.send(description, suppress_embeds=True)
                self.requests[request_id] = (track, message)
                data = {
                    "request_id": request_id,
                    "track_slug": track,
                    "message_id": message.id,
                }
                self.conn.execute(QUERY["add_request"], data)
            await asyncio.sleep(2)

        for request_id, (track, message) in list(self.requests.items()):
            if request_id in current_request_ids:
                continue
            await message.delete()
            del self.requests[request_id]
            self.conn.execute(QUERY["del_request"], {"request_id": request_id})

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Fetch tracks and configure threads as needed."""
        await self.load_data()
        self.update_mentor_requests.start()  # pylint: disable=E1101

    @commands.is_owner()
    @commands.dm_only()
    @commands.command()
    async def requests_reload(self, ctx: commands.Context) -> None:
        """Command to reload data."""
        _ = ctx  # unused
        await self.load_data()

    @commands.is_owner()
    @commands.dm_only()
    @commands.command()
    async def requests_stats(self, ctx: commands.Context) -> None:
        """Command to dump stats."""
        msg = f"{len(self.requests)=}, {len(self.tracks)=}"
        await ctx.reply(msg)

    async def load_data(self) -> None:
        """Load Exercism data."""
        guild = self.bot.get_guild(self.exercism_guild_id)
        assert guild is not None
        self.tracks = await self.exercism.all_tracks()
        self.tracks.sort()

        cur = self.conn.execute(QUERY["get_theads"])
        self.threads = {}
        for track_slug, message_id in cur.fetchall():
            thread = guild.get_thread(message_id)
            assert thread is not None
            self.threads[track_slug] = thread

        channel = guild.get_channel(self.channel_id)
        assert isinstance(channel, discord.TextChannel)
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
            assert message is not None
            self.requests[request_id] = (track_slug, message)

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
