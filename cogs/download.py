"""Download public videos from a small allowlist of supported platforms."""
from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import discord
from discord import app_commands
from discord.ext import commands
from yt_dlp import YoutubeDL

log = logging.getLogger(__name__)
MAX_BYTES = 8 * 1024 * 1024
ALLOWED_HOSTS = {
    "youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "www.youtu.be",
    "instagram.com", "www.instagram.com",
    "facebook.com", "www.facebook.com", "m.facebook.com", "fb.watch",
    "tiktok.com", "www.tiktok.com", "m.tiktok.com", "vm.tiktok.com", "vt.tiktok.com",
}


def validate_url(url: str) -> str | None:
    parsed = urlparse(url.strip())
    if parsed.scheme != "https" or not parsed.hostname:
        return None
    host = parsed.hostname.lower().rstrip(".")
    if host not in ALLOWED_HOSTS:
        return None
    return url.strip()


def download_sync(url: str, folder: str) -> Path:
    output = str(Path(folder) / "clip.%(ext)s")
    opts = {
        "outtmpl": output,
        "format": "best[filesize<=8388608]/best[height<=480][filesize<=8388608]/worst[filesize<=8388608]",
        "max_filesize": MAX_BYTES,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 15,
        "retries": 1,
        "overwrites": True,
    }
    with YoutubeDL(opts) as ydl:
        ydl.download([url])
    files = [p for p in Path(folder).iterdir() if p.is_file() and p.name != "clip.part"]
    if not files:
        raise RuntimeError("No downloadable video was returned.")
    file_path = max(files, key=lambda p: p.stat().st_size)
    if file_path.stat().st_size > MAX_BYTES:
        file_path.unlink(missing_ok=True)
        raise ValueError("The video is larger than Clipy's 8 MB attachment limit.")
    return file_path


class DownloadCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def send_download(self, url: str, send_file):
        safe_url = validate_url(url)
        if not safe_url:
            await send_file(error="Unsupported link. Use a public HTTPS video link from YouTube, Instagram, Facebook, or TikTok.")
            return
        with tempfile.TemporaryDirectory(prefix="clipy_") as folder:
            try:
                path = await asyncio.wait_for(asyncio.to_thread(download_sync, safe_url, folder), timeout=90)
                await send_file(path=path)
            except asyncio.TimeoutError:
                await send_file(error="Download timed out. Try a shorter or different public video.")
            except Exception as exc:
                log.info("Download failed (%s): %s", urlparse(safe_url).hostname, type(exc).__name__)
                await send_file(error="Couldn't download this video. It may be private, restricted, unsupported, or too large. Try another public link.")

    @app_commands.command(name="download", description="Download a public video from a supported platform.")
    @app_commands.describe(link="Public video URL from YouTube, Instagram, Facebook, or TikTok.")
    @app_commands.checks.cooldown(1, 20.0)
    async def slash_download(self, interaction: discord.Interaction, link: str):
        await interaction.response.defer(thinking=True, ephemeral=True)

        async def respond(*, path: Path | None = None, error: str | None = None):
            if error:
                await interaction.followup.send(error, ephemeral=True)
            else:
                await interaction.followup.send(file=discord.File(path, filename=path.name), ephemeral=True)

        await self.send_download(link, respond)

    @commands.command(name="download")
    @commands.cooldown(1, 20.0, commands.BucketType.user)
    async def prefix_download(self, ctx: commands.Context, *, link: str):
        async def respond(*, path: Path | None = None, error: str | None = None):
            if error:
                await ctx.reply(error, mention_author=False)
            else:
                await ctx.reply(file=discord.File(path, filename=path.name), mention_author=False)

        await self.send_download(link, respond)


async def setup(bot: commands.Bot):
    await bot.add_cog(DownloadCommands(bot))
