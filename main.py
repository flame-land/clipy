"""Clipy Discord bot entry point."""
from __future__ import annotations
import asyncio
import logging
import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
log = logging.getLogger("clipy")


def configured_prefix():
    return os.getenv("BOT_PREFIX", "!").strip() or "!"


def configured_intents():
    intents = discord.Intents.default()
    intents.message_content = True
    return intents


def configured_activity_messages():
    """Read activity messages separated by |, falling back to the single activity name."""
    raw = os.getenv("BOT_ACTIVITY_MESSAGES", "").strip()
    messages = [item.strip() for item in raw.split("|") if item.strip()]
    if not messages:
        fallback = os.getenv("BOT_ACTIVITY_NAME", "/clip search").strip()
        messages = [fallback] if fallback else []
    return messages


def make_activity(activity_type, activity_name):
    if not activity_name:
        return None
    if activity_type == "playing":
        return discord.Game(name=activity_name)
    if activity_type == "streaming":
        stream_url = os.getenv("BOT_STREAM_URL", "").strip()
        if stream_url.startswith(("https://twitch.tv/", "https://www.twitch.tv/", "https://youtube.com/", "https://www.youtube.com/")):
            return discord.Streaming(name=activity_name, url=stream_url)
        log.warning("Streaming activity requires a Twitch or YouTube BOT_STREAM_URL; using watching instead.")
        return discord.Activity(type=discord.ActivityType.watching, name=activity_name)
    activity_types = {
        "listening": discord.ActivityType.listening,
        "watching": discord.ActivityType.watching,
        "competing": discord.ActivityType.competing,
    }
    return discord.Activity(type=activity_types.get(activity_type, discord.ActivityType.listening), name=activity_name)


class ClipyBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=commands.when_mentioned_or(configured_prefix()),
            intents=configured_intents(),
            help_command=None,
        )
        self._presence_task = None

    async def setup_hook(self):
        await self.load_extension("cogs.clip")
        await self.load_extension("cogs.download")
        guild_id = os.getenv("DEV_GUILD_ID", "").strip()
        if guild_id.isdigit():
            guild = discord.Object(id=int(guild_id))
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
        else:
            synced = await self.tree.sync()
        log.info("Synced %d application commands", len(synced))

    async def on_ready(self):
        status_name = os.getenv("BOT_STATUS", "online").strip().lower()
        statuses = {
            "online": discord.Status.online,
            "idle": discord.Status.idle,
            "dnd": discord.Status.dnd,
            "invisible": discord.Status.invisible,
        }
        status = statuses.get(status_name, discord.Status.online)
        self._presence_status = status
        if self._presence_task is None or self._presence_task.done():
            self._presence_task = asyncio.create_task(self.rotate_presence())
        log.info("Logged in as %s", self.user)

    async def rotate_presence(self):
        messages = configured_activity_messages()
        if not messages:
            await self.change_presence(status=self._presence_status, activity=None)
            return
        try:
            interval = max(15, int(os.getenv("BOT_ACTIVITY_INTERVAL", "30")))
        except ValueError:
            interval = 30
        activity_type = os.getenv("BOT_ACTIVITY_TYPE", "listening").strip().lower()
        index = 0
        while not self.is_closed():
            activity = make_activity(activity_type, messages[index % len(messages)])
            await self.change_presence(status=self._presence_status, activity=activity)
            index += 1
            await asyncio.sleep(interval)


def main():
    token = os.getenv("DISCORD_TOKEN", "").strip()
    if not token or token == "put_your_bot_token_here":
        raise SystemExit("Missing DISCORD_TOKEN. Add your token to a local .env file.")
    ClipyBot().run(token, log_handler=None)


if __name__ == "__main__":
    main()
