"""Clipy Discord bot entry point."""
from __future__ import annotations
import logging, os
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
log = logging.getLogger("clipy")

class ClipyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.default())

    async def setup_hook(self):
        await self.load_extension("cogs.clip")
        await self.load_extension("cogs.errors")
        guild_id = os.getenv("DEV_GUILD_ID", "").strip()
        if guild_id.isdigit():
            guild = discord.Object(id=int(guild_id))
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
        else:
            synced = await self.tree.sync()
        log.info("Synced %d application commands", len(synced))

    async def on_ready(self):
        log.info("Logged in as %s", self.user)
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="/clip search"))

def main():
    token = os.getenv("DISCORD_TOKEN", "").strip()
    if not token or token == "put_your_bot_token_here":
        raise SystemExit("Missing DISCORD_TOKEN. Add your token to a local .env file.")
    ClipyBot().run(token, log_handler=None)

if __name__ == "__main__":
    main()
