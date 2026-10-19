"""Clipy slash and prefix commands."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import random

import discord
from discord import app_commands
from discord.ext import commands

from services.search import search_youtube
from utils.components import ClipResultsView, status_view

log = logging.getLogger(__name__)

RANDOM_QUERIES = (
    "Dragon Ball iconic scene",
    "anime fight scene",
    "Goku Black scene",
    "Jujutsu Kaisen fight scene",
    "Naruto iconic scene",
    "One Piece fight scene",
)


def prefix_text(ctx: commands.Context | None = None) -> str:
    """Get the configured prefix for this server or the default prefix."""
    default = os.getenv("BOT_PREFIX", "!").strip() or "!"
    if ctx is not None and ctx.guild is not None:
        return getattr(ctx.bot, "guild_prefixes", {}).get(str(ctx.guild.id), default)
    return default


def help_message(prefix: str | None = None) -> str:
    p = discord.utils.escape_markdown(prefix or prefix_text())
    return (
        "**Slash commands**\n"
        "`/clip search <clip>` — search YouTube (short or long videos)\n"
        "`/clip random` — find a random anime scene\n"
        "`/clip sources` — supported download sources\n"
        "`/clip help` — show this guide\n"
        "`/clip ping` — check latency\n"
        "`/download <link>` — download the first 60 seconds of a public video\n"
        "`/bgremove` — open the green-screen tool\n\n"
        "`/editor` — get tailored editing advice and optional video feedback\n"
        "`/editor-enable channel:<channel>` / `/editor-disable channel:<channel>` — manage the editing coach (Manage Server)\n"
        "**Prefix commands**\n"
        f"`{p}clip search <keywords>`\n"
        f"`{p}clip random`\n"
        f"`{p}clip sources`\n"
        f"`{p}download <URL>`\n"
        f"`{p}bgremove` — open the green-screen tool\n"
        f"`{p}agent enable #channel` / `{p}agent disable #channel` — control the editing coach (Manage Server)\n"
        f"`{p}help`\n"
        f"`{p}prefix <new-prefix>` — change this server's prefix (Manage Server permission)\n"
        f"`{p}ping`\n\n"
        "You can also mention Clipy before a prefix command."
    )


def source_message() -> str:
    return (
        "**Clip search**\nYouTube search · includes short clips and full-length videos\n\n"
        "**Public-link downloads**\nYouTube, Instagram, Facebook, TikTok, Vimeo, Reddit, "
        "X/Twitter, Dailymotion, Streamable, Twitch clips, Pinterest, and Tumblr.\n\n"
        "Support varies by site and individual link. Private, restricted, or unavailable "
        "content may not work. Downloads are limited to the first 60 seconds."
    )


class ClipCommands(
    commands.GroupCog,
    group_name="clip",
    description="Search YouTube videos and download public video links.",
):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.command(name="search", description="Search YouTube for short or long videos.")
    @app_commands.describe(clip="What scene, clip, or video should Clipy find?")
    @app_commands.checks.cooldown(1, 8.0)
    async def search(self, interaction: discord.Interaction, clip: str):
        query = " ".join(clip.split()).strip()
        if len(query) < 2:
            await interaction.response.send_message(
                view=status_view("Search too short", "Add a few more words."), ephemeral=True
            )
            return
        if len(query) > 180:
            await interaction.response.send_message(
                view=status_view("Search too long", "Keep it under 180 characters."), ephemeral=True
            )
            return

        await interaction.response.defer(thinking=True)
        try:
            results = await search_youtube(query, limit=9)
        except asyncio.TimeoutError:
            await interaction.followup.send(
                view=status_view("Search timed out", "Try again in a moment."), ephemeral=True
            )
            return
        except Exception:
            log.exception("YouTube search failed for query %r", query)
            await interaction.followup.send(
                view=status_view("Search failed", "Try again in a bit."), ephemeral=True
            )
            return

        if not results:
            await interaction.followup.send(
                view=status_view(
                    "No results",
                    f"No YouTube videos found for {discord.utils.escape_markdown(query)}. Try different keywords.",
                ),
                ephemeral=True,
            )
            return
        await interaction.followup.send(view=ClipResultsView(query, results, interaction.user.id))

    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.command(name="random", description="Search for a random anime scene.")
    @app_commands.checks.cooldown(1, 8.0)
    async def random_clip(self, interaction: discord.Interaction):
        query = random.choice(RANDOM_QUERIES)
        await interaction.response.defer(thinking=True)
        try:
            results = await search_youtube(query, limit=9)
        except Exception:
            log.exception("Random search failed")
            await interaction.followup.send(
                view=status_view("Search failed", "Try again in a bit."), ephemeral=True
            )
            return
        if not results:
            await interaction.followup.send(
                view=status_view("No results", "Try `/clip search` with different keywords."),
                ephemeral=True,
            )
            return
        await interaction.followup.send(view=ClipResultsView(query, results, interaction.user.id))

    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.command(name="sources", description="Show search and download sources.")
    async def sources(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            view=status_view("Sources", source_message()), ephemeral=True
        )

    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.command(name="help", description="Show Clipy's available commands.")
    async def help_command(self, interaction: discord.Interaction):
        prefix = getattr(self.bot, "guild_prefixes", {}).get(
            str(interaction.guild_id), prefix_text()
        )
        await interaction.response.send_message(
            view=status_view("Clipy commands", help_message(prefix)), ephemeral=True
        )

    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.command(name="bgremove", description="Open the AI green-screen tool for photos and videos.")
    async def bgremove(self, interaction: discord.Interaction):
        url = os.getenv("BGREMOVER_URL", "").strip().rstrip("/")
        if not url.startswith(("https://", "http://")):
            await interaction.response.send_message(view=status_view("Green-screen tool", "The website link has not been configured yet. Ask a server admin to set BGREMOVER_URL."), ephemeral=True)
            return
        await interaction.response.send_message(view=status_view("AI green screen", f"Remove the background from a photo or short video, then download it with a solid green background.\n\n[Open BGremover]({url})\n\nPhotos: PNG, JPG, WebP, BMP · Videos: MP4, MOV, MKV, WebM, AVI."))

    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.command(name="ping", description="Check Clipy's response latency.")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            view=status_view("Pong", f"Gateway latency: {round(self.bot.latency * 1000)} ms"),
            ephemeral=True,
        )

    @commands.group(name="clip", invoke_without_command=True)
    async def prefix_clip(self, ctx: commands.Context):
        p = prefix_text(ctx)
        await ctx.send(
            view=status_view(
                "Clip commands",
                f"Try `{p}clip search <keywords>`, `{p}clip random`, or `{p}clip sources`.",
            )
        )

    @prefix_clip.command(name="search")
    @commands.cooldown(1, 8.0, commands.BucketType.user)
    async def prefix_search(self, ctx: commands.Context, *, clip: str):
        query = " ".join(clip.split()).strip()
        if len(query) < 2 or len(query) > 180:
            await ctx.send(view=status_view("Invalid search", "Use between 2 and 180 characters."))
            return
        async with ctx.typing():
            try:
                results = await search_youtube(query, limit=9)
            except Exception:
                log.exception("Prefix YouTube search failed for query %r", query)
                await ctx.send(view=status_view("Search failed", "Try again in a bit."))
                return
        if not results:
            await ctx.send(
                view=status_view(
                    "No results",
                    f"No YouTube videos matched {discord.utils.escape_markdown(query)}.",
                )
            )
            return
        await ctx.send(view=ClipResultsView(query, results, ctx.author.id))

    @prefix_clip.command(name="random")
    @commands.cooldown(1, 8.0, commands.BucketType.user)
    async def prefix_random(self, ctx: commands.Context):
        query = random.choice(RANDOM_QUERIES)
        async with ctx.typing():
            try:
                results = await search_youtube(query, limit=9)
            except Exception:
                log.exception("Prefix random search failed")
                await ctx.send(view=status_view("Search failed", "Try again in a bit."))
                return
        if not results:
            await ctx.send(view=status_view("No results", "Try another search."))
            return
        await ctx.send(view=ClipResultsView(query, results, ctx.author.id))

    @prefix_clip.command(name="sources")
    async def prefix_sources(self, ctx: commands.Context):
        await ctx.send(view=status_view("Sources", source_message()))

    @commands.command(name="prefix")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def prefix_set(self, ctx: commands.Context, new_prefix: str):
        """Set this server's prefix. Requires Manage Server permission."""
        new_prefix = new_prefix.strip()
        if not new_prefix or len(new_prefix) > 5 or any(char.isspace() for char in new_prefix):
            await ctx.send(view=status_view(
                "Invalid prefix",
                "Choose a prefix 1–5 characters long with no spaces. Example: `!prefix ?`",
            ))
            return

        bot = ctx.bot
        guild_id = str(ctx.guild.id)
        previous = getattr(bot, "guild_prefixes", {}).get(guild_id, prefix_text())
        bot.guild_prefixes[guild_id] = new_prefix
        try:
            from main import PREFIX_STORE
            PREFIX_STORE.parent.mkdir(parents=True, exist_ok=True)
            PREFIX_STORE.write_text(
                json.dumps(bot.guild_prefixes, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        except OSError:
            bot.guild_prefixes[guild_id] = previous
            await ctx.send(view=status_view(
                "Could not save prefix", "I couldn't write the prefix settings to disk. Try again later."
            ))
            return
        await ctx.send(view=status_view(
            "Server prefix updated",
            f"This server's prefix is now `{discord.utils.escape_markdown(new_prefix)}`. "
            f"Use `{discord.utils.escape_markdown(new_prefix)}help` for the updated command guide.",
        ))

    @commands.command(name="help")
    async def prefix_help(self, ctx: commands.Context):
        await ctx.send(view=status_view("Clipy commands", help_message(prefix_text(ctx))))

    @commands.command(name="bgremove")
    async def prefix_bgremove(self, ctx: commands.Context):
        url = os.getenv("BGREMOVER_URL", "").strip().rstrip("/")
        if not url.startswith(("https://", "http://")):
            await ctx.send(view=status_view("Green-screen tool", "The website link has not been configured yet. Ask a server admin to set BGREMOVER_URL."))
            return
        await ctx.send(view=status_view("AI green screen", f"Remove the background from a photo or short video, then download it with a solid green background.\n\n[Open BGremover]({url})\n\nPhotos: PNG, JPG, WebP, BMP · Videos: MP4, MOV, MKV, WebM, AVI."))

    @commands.command(name="ping")
    async def prefix_ping(self, ctx: commands.Context):
        await ctx.send(
            view=status_view("Pong", f"Gateway latency: {round(self.bot.latency * 1000)} ms")
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(ClipCommands(bot))
