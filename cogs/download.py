"""Redirect Clipy download commands to the BGremover website downloader."""
from __future__ import annotations

import os

import discord
from discord import app_commands
from discord.ext import commands

from utils.components import status_view


def downloader_url() -> str:
    return os.getenv("BGREMOVER_URL", "").strip().rstrip("/")


def downloader_view() -> discord.ui.LayoutView:
    url = downloader_url()
    if not url.startswith("https://"):
        return status_view(
            "Downloader unavailable",
            "The BGremover website URL has not been configured yet. Set `BGREMOVER_URL` in the bot environment.",
        )
    target = f"{url}/#video-downloader"
    return status_view(
        "Clipy Downloader",
        f"Use the website to download public videos or audio. Paste a link, choose quality and format, then download your file.\n\n[Open Video & Audio Downloader]({target})",
    )


class DownloadCommands(commands.Cog):
    """Send users to BGremover website downloads."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.command(name="download", description="Open the website video and audio downloader.")
    async def slash_download(self, interaction: discord.Interaction):
        await interaction.response.send_message(view=downloader_view(), ephemeral=True)

    @commands.command(name="download")
    async def prefix_download(self, ctx: commands.Context):
        await ctx.reply(view=downloader_view(), mention_author=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(DownloadCommands(bot))
