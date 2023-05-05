"""A web application to display Discord bot details."""

import datetime

from discord.ext import commands
import aiohttp.web


class WebApp:
    """Web application for the Bot."""

    def __init__(self, bot: commands.Bot) -> None:
        """Initialize."""
        self.bot = bot
        self.start_time = datetime.datetime.now()

    async def webstats(self, request: aiohttp.web.Request) -> aiohttp.web.Response:
        """Displays stats."""
        _ = request
        data = []
        data.append(f"Uptime: {datetime.datetime.now() - self.start_time}")
        data.append("")
        data.append("== Internals ==")
        data.append(f"{self.bot.command_prefix=}")
        data.append(f"{self.bot.owner_id=}")
        data.append(f"{self.bot.extensions=}")
        data.append(f"{self.bot.guilds=}")
        data.append(f"{self.bot.latency=}")
        data.append(f"{self.bot.private_channels=}")
        data.append(f"{self.bot.status=}")
        data.append(f"{self.bot.tree=}")
        data.append("")
        data.append("== Cog Details ==")
        for name, cog in self.bot.cogs.items():
            if hasattr(cog, "details"):
                data.append(f"{name}: {cog.details()}")
            else:
                data.append(f"{name}: <no details>")
        return aiohttp.web.Response(text="\n".join(data) + "\n")

    async def start_web(self, host: str, port: int) -> aiohttp.web.AppRunner:
        """Start the web application."""
        app = aiohttp.web.Application()
        app.add_routes([aiohttp.web.get("/", self.webstats)])
        runner = aiohttp.web.AppRunner(app, access_log=None)
        await runner.setup()
        await aiohttp.web.TCPSite(runner, host, port).start()
        return runner
