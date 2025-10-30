"""Discord module to publish mentor request queues. Version 2."""

import asyncio
import datetime
import enum
import logging
import random
import re
import statistics
import time
from typing import Sequence

import discord
import prometheus_client  # type: ignore
from discord.ext import commands
from discord.ext import tasks
from exercism_lib import exercism

from cogs import base_cog

logger = logging.getLogger(__name__)

PROM_PREFIX = "mentor_request"
PROM_EXERCISM_REQUESTS = prometheus_client.Counter(
    f"{PROM_PREFIX}_exercism_rpc_total", "Number of API calls to Exercism", ["track"]
)
# write=False for reads; write=True for post message/delete message.
PROM_DISCORD_REQUESTS = prometheus_client.Counter(
    f"{PROM_PREFIX}_discord_rpc_total", "Number of API calls to Discord", ["write"]
)
PROM_TASK_QUEUE = prometheus_client.Gauge("mentor_requests_task_queue", "size of the task queue")
PROM_EXERCISM_INTERVAL = prometheus_client.Gauge(
    f"{PROM_PREFIX}_exercism_interval_seconds", "delay between refreshes", ["track"]
)
PROM_AVG_REQUEST_INTERVAL = prometheus_client.Gauge(
    f"{PROM_PREFIX}_avg_interval_seconds", "average delay between requests", ["track"]
)
PROM_REQUESTS_SEEN = prometheus_client.Counter(
    f"{PROM_PREFIX}_requests_seen_total", "requests seen", ["track"]
)

EXERCISM_TRACK_POLL_MIN_SECONDS = 5 * 60  # 5 minutes
EXERCISM_TRACK_POLL_MAX_SECONDS = 30 * 60  # 30 minutes
DISCORD_THREAD_POLL_SECONDS = 60 * 60  # 1 hour


class TaskType(enum.IntEnum):
    """Types of tasks to execute."""
    TASK_QUERY_EXERCISM = enum.auto()
    TASK_QUERY_DISCORD = enum.auto()
    TASK_DISCORD_ADD = enum.auto()
    TASK_DISCORD_DEL = enum.auto()


class RequestNotifier(base_cog.BaseCog):
    """Update Discord with Mentor Requests."""

    qualified_name = "Request Notifier v2"

    def __init__(
        self,
        bot: commands.Bot,
        channel_id: int,
        tracks: Sequence[str] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(bot=bot, **kwargs)
        self.exercism = exercism.AsyncExercism()
        self.channel_id = channel_id

        self.threads: dict[str, discord.Thread] = {}
        self.requests: dict[str, dict[str, str]] = {}
        self.messages: dict[str, dict[str, int]] = {}
        self.next_task_time = 0

        self.lock = asyncio.Lock()
        self.queue: asyncio.PriorityQueue[
            tuple[int, TaskType, str, str | None]
        ] = asyncio.PriorityQueue()

        if tracks:
            self.tracks = list(tracks)
        else:
            self.tracks = exercism.Exercism().all_tracks()
        self.tracks.sort()
        # Default to 10 minute polling.
        self.request_interval = {track: 600 for track in self.tracks}
        self.request_timestamps: dict[str, list[int]] = {track: [] for track in self.tracks}
        self.request_sum_delay: dict[str, int] = {track: 0 for track in self.tracks}
        self.request_counts: dict[str, int] = {track: 0 for track in self.tracks}

        self.task_manager.start()  # pylint: disable=E1101

    async def get_thread(self, track: str) -> discord.Thread:
        """Return the request thread for a specific track."""
        thread = self.threads.get(track)
        if not thread:
            raise LookupError(f"Failed to find track {track} in threads")

        # Refresh the thread object. This is helpful to update the is_archived bit.
        async with asyncio.timeout(10):
            got = await self.bot.fetch_channel(thread.id)
        assert isinstance(got, discord.Thread), f"Expected a Thread. {got=}"
        self.threads[track] = got
        return got

    @tasks.loop(seconds=5)
    async def task_manager(self):
        """Task loop."""
        if self.lock.locked():
            return
        async with self.lock:
            try:
                PROM_TASK_QUEUE.set(self.queue.qsize())
                now = int(time.time())
                # If the queue is empty or the next task is not yet due, return.
                if now < self.next_task_time or self.queue.empty():
                    return
                task = self.queue.get_nowait()
                task_time, task_type, track, details = task
                # If the next task is not yet due, queue it and return.
                if now < task_time:
                    self.queue.put_nowait(task)
                    self.next_task_time = task_time
                    return
                # Handle a task.
                if task_type == TaskType.TASK_QUERY_EXERCISM:
                    try:
                        await self.fetch_track_requests(track)
                    except asyncio.TimeoutError:
                        logger.exception("TimeoutError during fetch_track_requests(%s)", track)
                    finally:
                        self.queue_query_exercism(track)
                elif task_type == TaskType.TASK_QUERY_DISCORD:
                    try:
                        await self.fetch_discord_thread(track)
                    finally:
                        self.queue_query_discord(track)
                elif task_type == TaskType.TASK_DISCORD_ADD:
                    await self.update_discord_add(track, details)
                elif task_type == TaskType.TASK_DISCORD_DEL:
                    await self.update_discord_del(track, details)
                else:
                    logger.exception("Unknown task type, %d", task_type)

            except Exception:  # pylint: disable=broad-exception-caught
                logger.exception("Unhandled exception in task manager loop.")

    @task_manager.before_loop
    async def before_task_manager(self):
        """Before starting the task manager, wait for ready and load Discord messages."""
        logger.debug("Start before_task_manager()")
        await self.bot.wait_until_ready()
        await self.load_data()
        self.populate_task_queue()
        logger.debug("End before_task_manager()")

    def exercism_poll_interval(self, track: str) -> int:
        """Return the poll interval between getting requests for a track."""
        interval = self.request_interval[track]
        times = self.request_timestamps[track]
        if len(times) < 2:
            self.request_interval[track] = min(int(1.5 * interval), EXERCISM_TRACK_POLL_MAX_SECONDS)
            return interval
        times.sort()
        intervals = [a - b for a, b in zip(times[1:], times)]
        # Clamp between EXERCISM_TRACK_POLL_MIN_SECONDS, EXERCISM_TRACK_POLL_MAX_SECONDS
        return min(
            max(int(statistics.mean(intervals) * 0.90), EXERCISM_TRACK_POLL_MIN_SECONDS),
            EXERCISM_TRACK_POLL_MAX_SECONDS,
        )

    async def fetch_track_requests(self, track: str) -> None:
        """Fetch the requests for a given track. Queue tasks to update the Discord thread."""
        logger.debug("Start fetch_track_requests(%s)", track)
        if track not in self.messages:
            return
        PROM_EXERCISM_REQUESTS.labels(track).inc()
        # fetch requests
        # update DB
        # update request interval data
        # compare to Discord thread; queue tasks to add/remove.
        async with asyncio.timeout(30):
            requests = await self.get_requests(track)
        logger.debug("Found %d requests for %s.", len(requests), track)

        add_requests = set(requests) - set(self.messages[track])
        del_requests = set(self.messages[track]) - set(requests)
        self.requests[track] = {
            request_id: message
            for request_id, (timestamp, message) in requests.items()
        }

        if add_requests:
            new_request_timestamps = [
                timestamp
                for request_id, (timestamp, message) in requests.items()
                if request_id in add_requests
            ]
            new_request_timestamps.sort(reverse=True)

            # Add the new sum intervals to the total and bump the count.
            prior_ts = []
            if self.request_timestamps[track]:
                prior_ts.append(max(self.request_timestamps[track]))
            self.request_sum_delay[track] += sum(
                a - b
                for a, b in zip(new_request_timestamps, new_request_timestamps[1:] + prior_ts)
            )
            self.request_counts[track] += len(add_requests)
            PROM_AVG_REQUEST_INTERVAL.labels(track).set(
                int(self.request_sum_delay[track] / self.request_counts[track])
            )
            PROM_REQUESTS_SEEN.labels(track).inc(len(add_requests))

            # Add the new timestamps the the running tally of the last N.
            self.request_timestamps[track] = sorted(
                self.request_timestamps[track] + new_request_timestamps,
                reverse=True
            )[:15]

            for request_id in add_requests:
                logger.debug("Queue TASK_DISCORD_ADD %s %s for now", track, request_id)
                self.queue.put_nowait((0, TaskType.TASK_DISCORD_ADD, track, request_id))

        for request_id in list(del_requests)[:10]:
            logger.debug("Queue TASK_DISCORD_DEL %s %s for now", track, request_id)
            self.queue.put_nowait((0, TaskType.TASK_DISCORD_DEL, track, request_id))

    def queue_query_exercism(self, track: str) -> None:
        """Queue a task to query Exercism for a track."""
        interval = self.exercism_poll_interval(track)
        PROM_EXERCISM_INTERVAL.labels(track).set(interval)
        task_time = int(time.time()) + interval
        logger.debug("Queue TASK_QUERY_EXERCISM %s in %d seconds", track, interval)
        self.queue.put_nowait((task_time, TaskType.TASK_QUERY_EXERCISM, track, None))

    async def fetch_discord_thread(self, track: str) -> None:
        """Fetch a track thread from Discord to update the local cache."""
        logger.debug("Start fetch_discord_thread(%s)", track)
        request_url_re = re.compile(r"\bhttps://exercism.org/mentoring/requests/(\w+)\b")
        PROM_DISCORD_REQUESTS.labels(False).inc()
        thread = await self.get_thread(track)
        messages = {}
        await self.unarchive(thread)
        async for message in thread.history(limit=None):
            if message.author != thread.owner:
                continue
            if message == thread.starter_message:
                continue
            match = request_url_re.search(message.content)
            if match is None:
                continue
            messages[str(match.group(1))] = message.id
        self.messages[track] = messages

    def queue_query_discord(self, track: str) -> None:
        """Queue a task to query a Discord request thread."""
        interval = DISCORD_THREAD_POLL_SECONDS
        task_time = int(time.time()) + interval
        logger.debug("Queue TASK_QUERY_DISCORD %s in %d seconds", track, interval)
        self.queue.put_nowait((task_time, TaskType.TASK_QUERY_DISCORD, track, None))

    async def update_discord_add(self, track: str, request_id: str) -> None:
        """Add a request message to Discord."""
        logger.debug("Start update_discord_add(%s, %s)", track, request_id)
        PROM_DISCORD_REQUESTS.labels(True).inc()
        thread = await self.get_thread(track)
        description = self.requests[track][request_id]
        async with asyncio.timeout(10):
            message = await thread.send(description, suppress_embeds=True)
        self.messages[track][request_id] = message.id

    async def update_discord_del(self, track: str, request_id: str) -> None:
        """Remove a request message from Discord."""
        PROM_DISCORD_REQUESTS.labels(True).inc()
        logger.debug("Start update_discord_del(%s, %s)", track, request_id)
        thread = await self.get_thread(track)
        await self.unarchive(self.threads[track])

        message_id = next(
            (
                message_id for req, message_id in self.messages[track].items()
                if req == request_id
            ), None
        )
        if not message_id:
            return
        async with asyncio.timeout(5):
            try:
                await thread.get_partial_message(message_id).delete()
                del self.messages[track][request_id]
            except discord.errors.NotFound:
                pass

    def populate_task_queue(self):
        """Populate the initial task queue."""
        tracks = self.tracks.copy()
        random.shuffle(tracks)
        # Spread the initial requests over 5 minutes
        for track, offset in zip(tracks, range(0, 5 * 60, int(5 * 60 / len(tracks)))):
            task_time = int(time.time()) + offset
            self.queue.put_nowait((task_time, TaskType.TASK_QUERY_DISCORD, track, None))
            self.queue.put_nowait((task_time + 1, TaskType.TASK_QUERY_EXERCISM, track, None))

    async def unarchive(self, thread: discord.Thread) -> None:
        """Ensure a thread is not archived."""
        if not thread.archived:
            return
        async with asyncio.timeout(10):
            message = await thread.send("Sending a message to unarchive this thread.")
        async with asyncio.timeout(10):
            await message.delete()

    async def load_data(self) -> None:
        """Load Exercism data."""
        channel = self.bot.get_channel(self.channel_id)
        assert isinstance(channel, discord.TextChannel), f"{channel} is not a TextChannel."

        self.threads = {}
        async for message in channel.history(limit=None):
            if not message.thread:
                continue
            thread = await message.fetch_thread()
            self.threads[thread.name.lower()] = thread

        for track in self.tracks:
            if track in self.threads:
                continue
            thread = await channel.create_thread(
                name=track.title(),
                type=discord.ChannelType.public_thread,
            )
            self.threads[track] = thread
            await asyncio.sleep(2)

    async def get_requests(self, track_slug: str) -> dict[str, tuple[int, str]]:
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

            timestamp = int(datetime.datetime.fromisoformat(req["updated_at"]).timestamp())
            requests[req["uuid"]] = (timestamp, msg)
        return requests
