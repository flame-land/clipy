"""Clipy slash commands."""
from __future__ import annotations
import asyncio, logging, random
import discord
from discord import app_commands
from discord.ext import commands
from services.search import search_youtube
from utils.components import ClipResultsView, status_view

log = logging.getLogger(__name__)

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
            await interaction.followup.send(view=status_view("No results", f"No videos matched **{discord.utils.escape_markdown(query)}**. Try different keywords."), ephemeral=True)
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
            await interaction.followup.send(view=status_view("No results", "No clips came back this time. Try `/clip search`."), ephemeral=True)
            return
        await interaction.followup.send(view=ClipResultsView(query, results, interaction.user.id))

    @app_commands.command(name="sources", description="Show which search sources Clipy currently supports.")
    async def sources(self, interaction: discord.Interaction):
        await interaction.response.send_message(view=status_view("Source coverage", "**YouTube search:** enabled through yt-dlp metadata search.\n**Other platforms:** not integrated yet.\n\nClipy links to source pages and does not download or rehost videos in this version."), ephemeral=True)

    @app_commands.command(name="help", description="Show Clipy's available commands.")
    async def help_command(self, interaction: discord.Interaction):
        await interaction.response.send_message(view=status_view("Command guide", "`/clip search clip:<keywords>` — search for a scene\n`/clip random` — random anime-scene search\n`/clip sources` — see current provider coverage\n`/clip help` — show this guide\n`/ping` — check bot latency\n\nResults use Components V2, not embeds."), ephemeral=True)

    @app_commands.command(name="ping", description="Check Clipy's response latency.")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message(view=status_view("Pong", f"Gateway latency: **{round(self.bot.latency * 1000)} ms**"), ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(ClipCommands(bot))
