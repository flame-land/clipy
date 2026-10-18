"""Clipy slash and prefix commands."""
from __future__ import annotations

import asyncio
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


def prefix_text() -> str:
    return os.getenv("BOT_PREFIX", "!").strip() or "!"


def help_message() -> str:
    p = discord.utils.escape_markdown(prefix_text())
    return (
        "**Slash commands**\n"
        "`/clip search <clip>` — search YouTube\n"
        "`/clip random` — find a random anime scene\n"
        "`/clip sources` — supported download sources\n"
        "`/clip help` — show this guide\n"
        "`/clip ping` — check latency\n"
        "`/download <link>` — download a public clip\n\n"
        "**Prefix commands**\n"
        f"`{p}clip search <keywords>`\n"
        f"`{p}clip random`\n"
        f"`{p}clip sources`\n"
        f"`{p}download <URL>`\n"
        f"`{p}help`\n"
        f"`{p}ping`\n\n"
        "You can also mention the bot before a prefix command. Enable Message Content Intent "
        "in the Developer Portal for prefix and mention commands."
    )


def source_message() -> str:
    return (
        "**Clip search**\nYouTube only · results are limited to clips up to 60 seconds\n\n"
        "**Public-link downloads**\nYouTube, Instagram, Facebook, TikTok, Vimeo, Reddit, "
        "X/Twitter, Dailymotion, Streamable, Twitch clips, Pinterest, and Tumblr.\n\n"
        "Support varies by site and individual link. Private, restricted, or unavailable "
        "content may not work. Downloads are limited to the first 60 seconds."
    )


class ClipCommands(
    commands.GroupCog,
    group_name="clip",
    description="Find short clips and download public video links.",
):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="search", description="Search YouTube for a clip or scene.")
    @app_commands.describe(clip="What scene or clip should Clipy find?")
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
                    f"No short clips found for {discord.utils.escape_markdown(query)}. Try different keywords.",
                ),
                ephemeral=True,
            )
            return
        await interaction.followup.send(view=ClipResultsView(query, results, interaction.user.id))

    @app_commands.command(name="random", description="Search for a random anime scene.")
    @app_commands.checks.cooldown(1, 8.0)
    async def random_clip(self, interaction: discord.Interaction):
        query = random.choice(RANDOM_QUERIES)
        await interaction.response.defer(thinking=True)
        try:
            results = await search_youtube(query, limit=6)
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

    @app_commands.command(name="sources", description="Show search and download sources.")
    async def sources(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            view=status_view("Sources", source_message()), ephemeral=True
        )

    @app_commands.command(name="help", description="Show Clipy's available commands.")
    async def help_command(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            view=status_view("Clipy commands", help_message()), ephemeral=True
        )

    @app_commands.command(name="ping", description="Check Clipy's response latency.")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            view=status_view("Pong", f"Gateway latency: {round(self.bot.latency * 1000)} ms"),
            ephemeral=True,
        )

    @commands.group(name="clip", invoke_without_command=True)
    async def prefix_clip(self, ctx: commands.Context):
        p = prefix_text()
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
                    f"No short clips matched {discord.utils.escape_markdown(query)}.",
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
                results = await search_youtube(query, limit=6)
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

    @commands.command(name="help")
    async def prefix_help(self, ctx: commands.Context):
        await ctx.send(view=status_view("Clipy commands", help_message()))

    @commands.command(name="ping")
    async def prefix_ping(self, ctx: commands.Context):
        await ctx.send(
            view=status_view("Pong", f"Gateway latency: {round(self.bot.latency * 1000)} ms")
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(ClipCommands(bot))
