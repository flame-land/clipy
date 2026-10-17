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


def prefix_text():
    return os.getenv("BOT_PREFIX", "!").strip() or "!"


def help_message() -> str:
    p = discord.utils.escape_markdown(prefix_text())
    return (
        "**Slash commands**\n"
        "`/clip search <clip>` — search YouTube\n"
        "`/clip random` — random anime-scene search\n"
        "`/clip sources` — supported search/download sources\n"
        "`/clip help` — show this command list\n"
        "`/clip ping` — check latency\n"
        "`/download <link>` — download a supported public video\n\n"
        "**Prefix commands**\n"
        f"`{p}clip search <keywords>`\n"
        f"`{p}clip random`\n"
        f"`{p}clip sources`\n"
        f"`{p}download <URL>`\n"
        f"`{p}help`\n"
        f"`{p}ping`\n\n"
        "**Mention commands**\n"
        "`@Clipy clip search <keywords>`\n"
        "`@Clipy clip random`\n"
        "`@Clipy clip sources`\n"
        "`@Clipy download <URL>`\n"
        "`@Clipy help`\n"
        "`@Clipy ping`\n\n"
        "Replace `@Clipy` with the bot's actual mention."
    )


class ClipCommands(commands.GroupCog, group_name="clip", description="Find clips and videos from supported sources."):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="search", description="Search YouTube for a clip, scene, or video.")
    @app_commands.describe(clip="What scene or clip should Clipy find?")
    @app_commands.checks.cooldown(1, 8.0)
    async def search(self, interaction: discord.Interaction, clip: str):
        query = " ".join(clip.split()).strip()
        if len(query) < 2:
            await interaction.response.send_message(view=status_view("Query too short", "Enter at least two characters."), ephemeral=True)
            return
        if len(query) > 180:
            await interaction.response.send_message(view=status_view("Query too long", "Keep the query under 180 characters."), ephemeral=True)
            return
        await interaction.response.defer(thinking=True)
        try:
            results = await search_youtube(query, limit=9)
        except asyncio.TimeoutError:
            await interaction.followup.send(view=status_view("Search timed out", "The source took too long to respond. Try again shortly."), ephemeral=True)
            return
        except Exception:
            log.exception("YouTube search failed for query %r", query)
            await interaction.followup.send(view=status_view("Source unavailable", "YouTube search failed. Try again later."), ephemeral=True)
            return
        if not results:
            await interaction.followup.send(view=status_view("No results", f"No videos matched {discord.utils.escape_markdown(query)}. Try different keywords."), ephemeral=True)
            return
        await interaction.followup.send(view=ClipResultsView(query, results, interaction.user.id))

    @app_commands.command(name="random", description="Search a random anime scene query.")
    async def random_clip(self, interaction: discord.Interaction):
        query = random.choice(["Dragon Ball iconic scene", "anime fight scene", "Goku Black scene", "Jujutsu Kaisen fight scene", "Naruto iconic scene", "One Piece fight scene"])
        await interaction.response.defer(thinking=True)
        try:
            results = await search_youtube(query, limit=6)
        except Exception:
            log.exception("Random search failed")
            await interaction.followup.send(view=status_view("Source unavailable", "I couldn't reach the search source. Try again later."), ephemeral=True)
            return
        if not results:
            await interaction.followup.send(view=status_view("No results", "No clips came back this time. Try /clip search."), ephemeral=True)
            return
        await interaction.followup.send(view=ClipResultsView(query, results, interaction.user.id))

    @app_commands.command(name="sources", description="Show which search sources Clipy currently supports.")
    async def sources(self, interaction: discord.Interaction):
        await interaction.response.send_message(view=status_view("Sources", "Search: YouTube. Downloads: public videos from YouTube, Instagram, Facebook, and TikTok (up to 8 MB). Private or restricted videos may not work."), ephemeral=True)

    @app_commands.command(name="help", description="Show Clipy's available commands.")
    async def help_command(self, interaction: discord.Interaction):
        p = discord.utils.escape_markdown(prefix_text())
        await interaction.response.send_message(view=status_view("Clipy commands", help_message()), ephemeral=True)

    @app_commands.command(name="ping", description="Check Clipy's response latency.")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message(view=status_view("Pong", f"Gateway latency: {round(self.bot.latency * 1000)} ms"), ephemeral=True)

    @commands.group(name="clip", invoke_without_command=True)
    async def prefix_clip(self, ctx: commands.Context):
        p = prefix_text()
        await ctx.send(view=status_view("Clip commands", f"Try `{p}clip search <keywords>`, `{p}clip random`, or `{p}clip sources`."))

    @prefix_clip.command(name="search")
    async def prefix_search(self, ctx: commands.Context, *, clip: str):
        query = " ".join(clip.split()).strip()
        if len(query) < 2 or len(query) > 180:
            await ctx.send(view=status_view("Invalid query", "Enter a search query between 2 and 180 characters."))
            return
        async with ctx.typing():
            try:
                results = await search_youtube(query, limit=9)
            except Exception:
                log.exception("Prefix YouTube search failed for query %r", query)
                await ctx.send(view=status_view("Search failed", "Please try again shortly."))
                return
        if not results:
            await ctx.send(view=status_view("No results", f"No videos matched {discord.utils.escape_markdown(query)}."))
            return
        await ctx.send(view=ClipResultsView(query, results, ctx.author.id))

    @prefix_clip.command(name="random")
    async def prefix_random(self, ctx: commands.Context):
        query = random.choice(["Dragon Ball iconic scene", "anime fight scene", "Goku Black scene", "Jujutsu Kaisen fight scene", "Naruto iconic scene", "One Piece fight scene"])
        async with ctx.typing():
            try:
                results = await search_youtube(query, limit=6)
            except Exception:
                log.exception("Prefix random search failed")
                await ctx.send(view=status_view("Search failed", "Please try again shortly."))
                return
        if not results:
            await ctx.send(view=status_view("No results", "No clips came back this time."))
            return
        await ctx.send(view=ClipResultsView(query, results, ctx.author.id))

    @prefix_clip.command(name="sources")
    async def prefix_sources(self, ctx: commands.Context):
        await ctx.send(view=status_view("Sources", "Search: YouTube. Downloads: public videos from YouTube, Instagram, Facebook, and TikTok (up to 8 MB). Private or restricted videos may not work."))

    @commands.command(name="help")
    async def prefix_help(self, ctx: commands.Context):
        await ctx.send(view=status_view("Clipy commands", help_message()))

    @commands.command(name="ping")
    async def prefix_ping(self, ctx: commands.Context):
        await ctx.send(view=status_view("Pong", f"Gateway latency: {round(self.bot.latency * 1000)} ms"))


async def setup(bot: commands.Bot):
    await bot.add_cog(ClipCommands(bot))
