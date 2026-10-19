"""Clipy Discord bot entry point."""
from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("clipy")


def configured_prefix() -> str:
    return os.getenv("BOT_PREFIX", "!").strip() or "!"


PREFIX_STORE = Path(os.getenv("PREFIX_STORE", "data/prefixes.json"))


async def dynamic_prefix(bot: "ClipyBot", message: discord.Message):
    """Resolve a server-specific prefix, falling back to BOT_PREFIX."""
    prefix = configured_prefix()
    if message.guild is not None:
        prefix = bot.guild_prefixes.get(str(message.guild.id), prefix)
    return commands.when_mentioned_or(prefix)(bot, message)


def configured_intents() -> discord.Intents:
    intents = discord.Intents.default()
    intents.message_content = True
    return intents


def configured_activity_messages() -> list[str]:
    """Read activity messages separated by |, falling back to a single activity name."""
    raw = os.getenv("BOT_ACTIVITY_MESSAGES", "").strip()
    messages = [item.strip() for item in raw.split("|") if item.strip()]
    if not messages:
        fallback = os.getenv("BOT_ACTIVITY_NAME", "/clip search").strip()
        messages = [fallback] if fallback else []
    return messages


def make_activity(activity_type: str, activity_name: str) -> discord.BaseActivity | None:
    if not activity_name:
        return None
    if activity_type == "playing":
        return discord.Game(name=activity_name)
    if activity_type == "streaming":
        stream_url = os.getenv("BOT_STREAM_URL", "").strip()
        allowed_prefixes = (
            "https://twitch.tv/",
            "https://www.twitch.tv/",
            "https://youtube.com/",
            "https://www.youtube.com/",
        )
        if stream_url.startswith(allowed_prefixes):
            return discord.Streaming(name=activity_name, url=stream_url)
        log.warning(
            "Streaming activity requires a Twitch or YouTube BOT_STREAM_URL; using watching instead."
        )
        return discord.Activity(type=discord.ActivityType.watching, name=activity_name)

    activity_types = {
        "listening": discord.ActivityType.listening,
        "watching": discord.ActivityType.watching,
        "competing": discord.ActivityType.competing,
    }
    return discord.Activity(
        type=activity_types.get(activity_type, discord.ActivityType.listening),
        name=activity_name,
    )


def welcome_embed(guild: discord.Guild) -> discord.Embed:
    """Build the setup guide shared with a new server and its owner."""
    prefix = discord.utils.escape_markdown(configured_prefix())
    embed = discord.Embed(
        title="Thanks for adding Clipy! 🎬",
        description=(
            f"Thanks for inviting Clipy to **{discord.utils.escape_markdown(guild.name)}**!\n"
            "I'm a clip finder and public-video downloader. Here's how to get started."
        ),
        colour=discord.Colour.from_rgb(55, 145, 220),
    )
    embed.add_field(
        name="🔎 Find clips",
        value=(
            "`/clip search` — search YouTube for a scene or clip (up to 60 seconds).\n"
            "`/clip random` — discover a random anime scene.\n"
            f"`{prefix}clip search goku black` — prefix equivalent."
        ),
        inline=False,
    )
    embed.add_field(
        name="⬇️ Download public clips",
        value=(
            "`/download` or `!download <URL>` — open the download options. "
            "Clipy processes up to the first 60 seconds and offers video/audio formats. "
            "Only public links from supported sites may work."
        ),
        inline=False,
    )
    embed.add_field(
        name="🧭 Helpful commands",
        value=(
            "`/clip sources` — see supported sources.\n"
            "`/clip help` or `!help` — full command guide.\n"
            "`/clip ping` or `!ping` — check latency."
        ),
        inline=False,
    )
    embed.add_field(
        name="⚙️ Setup tips",
        value=(
            "No special welcome-channel setup is required. I'll post here if I can find a "
            "channel where I have permission to send messages. For prefix commands, enable "
            "**Message Content Intent** in the Discord Developer Portal. Downloads can fail "
            "if a site blocks access, the link is private, or the file exceeds Discord's upload limit."
        ),
        inline=False,
    )
    embed.set_footer(text="Use only content you have permission to download.")
    return embed


class ClipyBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=dynamic_prefix,
            intents=configured_intents(),
            help_command=None,
        )
        self._presence_task: asyncio.Task | None = None
        self.guild_prefixes: dict[str, str] = {}
        self.tree.on_error = self.on_app_command_error

    async def setup_hook(self):
        try:
            if PREFIX_STORE.exists():
                loaded = json.loads(PREFIX_STORE.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    self.guild_prefixes = {
                        str(guild_id): prefix
                        for guild_id, prefix in loaded.items()
                        if isinstance(guild_id, str) and isinstance(prefix, str)
                    }
        except (OSError, json.JSONDecodeError):
            log.exception("Could not load server prefixes from %s", PREFIX_STORE)
        await self.load_extension("cogs.clip")
        await self.load_extension("cogs.download")
        await self.load_extension("cogs.editor_agent")
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
        self._presence_status = statuses.get(status_name, discord.Status.online)
        if self._presence_task is None or self._presence_task.done():
            self._presence_task = asyncio.create_task(self.rotate_presence())
        log.info("Logged in as %s (ID: %s)", self.user, self.user.id if self.user else "unknown")

    async def on_guild_join(self, guild: discord.Guild):
        """Welcome new servers, then DM the owner; permission failures are non-fatal."""
        embed = welcome_embed(guild)
        bot_member = guild.me
        channel = guild.system_channel
        if bot_member is None:
            channel = None
        elif channel is None:
            channel = None
        else:
            permissions = channel.permissions_for(bot_member)
            if not (permissions.view_channel and permissions.send_messages and permissions.embed_links):
                channel = None

        if channel is None and bot_member is not None:
            channel = next(
                (
                    candidate
                    for candidate in guild.text_channels
                    if candidate.permissions_for(bot_member).view_channel
                    and candidate.permissions_for(bot_member).send_messages
                    and candidate.permissions_for(bot_member).embed_links
                ),
                None,
            )

        if channel is not None:
            try:
                await channel.send(embed=embed)
                log.info("Posted welcome message in #%s for guild %s (%s)", channel.name, guild.name, guild.id)
            except discord.HTTPException:
                log.warning("Could not post welcome message in guild %s (%s)", guild.name, guild.id)
        else:
            log.info("No suitable welcome channel available in guild %s (%s)", guild.name, guild.id)

        try:
            await guild.owner.send(embed=embed)
            log.info("Sent welcome DM to owner of guild %s (%s)", guild.name, guild.id)
        except (discord.Forbidden, discord.HTTPException, AttributeError):
            log.info("Could not DM owner of guild %s (%s); DMs may be disabled", guild.name, guild.id)

    async def on_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        if isinstance(error, app_commands.CommandOnCooldown):
            message = f"You're using commands too quickly. Try again in {error.retry_after:.1f}s."
        elif isinstance(error, app_commands.CheckFailure):
            message = "You can't use that command right now."
        else:
            log.error(
                "Application command failed (%s)",
                getattr(interaction.command, "qualified_name", "unknown"),
                exc_info=(type(error), error, error.__traceback__),
            )
            message = "Something went wrong. Please try again in a moment."

        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except discord.HTTPException:
            log.debug("Could not send application-command error response.")

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.reply(
                f"Slow down a little—try again in {error.retry_after:.1f}s.",
                mention_author=False,
                delete_after=8,
            )
        elif isinstance(error, commands.MissingPermissions):
            await ctx.reply(
                "You need the **Manage Server** permission to change this server's prefix.",
                mention_author=False,
                delete_after=10,
            )
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.reply(
                f"Missing argument: `{error.param.name}`. Use `{configured_prefix()}help` for help.",
                mention_author=False,
                delete_after=10,
            )
        elif isinstance(error, commands.CommandNotFound):
            return
        elif isinstance(error, commands.UserInputError):
            await ctx.reply(
                f"That command's input doesn't look right. Use `{configured_prefix()}help`.",
                mention_author=False,
                delete_after=10,
            )
        else:
            log.error(
                "Prefix command failed (%s)",
                getattr(ctx.command, "qualified_name", "unknown"),
                exc_info=(type(error), error, error.__traceback__),
            )
            await ctx.reply(
                "Something went wrong while running that command.",
                mention_author=False,
                delete_after=10,
            )

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
