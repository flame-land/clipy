"""Interactive public video/audio downloads for Clipy."""
from __future__ import annotations

import asyncio
import logging
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import discord
from discord import app_commands
from discord.ext import commands
from yt_dlp import YoutubeDL

from utils.components import ACCENT, status_view

log = logging.getLogger(__name__)
DEFAULT_MAX_BYTES = 25 * 1024 * 1024
DOWNLOAD_TIMEOUT = 180
ALLOWED_HOSTS = {
    "youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "www.youtu.be",
    "instagram.com", "www.instagram.com",
    "facebook.com", "www.facebook.com", "m.facebook.com", "fb.watch",
    "tiktok.com", "www.tiktok.com", "m.tiktok.com", "vm.tiktok.com", "vt.tiktok.com",
}
OPTIONS = {
    "video_best": ("Video · Best", "video", "bestvideo+bestaudio/best", None),
    "video_1080": ("Video · 1080p", "video", "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best", None),
    "video_720": ("Video · 720p", "video", "bestvideo[height<=720]+bestaudio/best[height<=720]/best", None),
    "video_480": ("Video · 480p", "video", "bestvideo[height<=480]+bestaudio/best[height<=480]/best", None),
    "video_360": ("Video · 360p", "video", "bestvideo[height<=360]+bestaudio/best[height<=360]/best", None),
    "audio_mp3": ("Audio · MP3", "audio", "bestaudio/best", "mp3"),
    "audio_m4a": ("Audio · M4A", "audio", "bestaudio[ext=m4a]/bestaudio/best", "m4a"),
}


def validate_url(url: str) -> str | None:
    parsed = urlparse(url.strip())
    if parsed.scheme != "https" or not parsed.hostname:
        return None
    if parsed.hostname.lower().rstrip(".") not in ALLOWED_HOSTS:
        return None
    return url.strip()


def download_sync(url: str, folder: str, option_key: str, max_bytes: int) -> Path:
    _, kind, format_selector, audio_codec = OPTIONS[option_key]
    output = str(Path(folder) / "clip.%(ext)s")
    opts = {
        "outtmpl": output,
        "format": format_selector,
        "max_filesize": max_bytes,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 20,
        "retries": 2,
        "overwrites": True,
        "merge_output_format": "mp4",
    }
    if audio_codec:
        opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": audio_codec,
            "preferredquality": "192",
        }]
    with YoutubeDL(opts) as ydl:
        ydl.download([url])

    files = [p for p in Path(folder).iterdir() if p.is_file() and not p.name.endswith(".part")]
    if not files:
        raise RuntimeError("No file was produced.")
    file_path = max(files, key=lambda p: p.stat().st_size)
    if file_path.stat().st_size > max_bytes:
        file_path.unlink(missing_ok=True)
        raise ValueError("The finished file exceeds this server's upload limit.")
    return file_path


class DownloadOptionsView(discord.ui.LayoutView):
    def __init__(self, url: str, requester_id: int, max_bytes: int, *, ephemeral: bool):
        super().__init__(timeout=180)
        self.url = url
        self.requester_id = requester_id
        self.max_bytes = max_bytes
        self.ephemeral = ephemeral
        box = discord.ui.Container(
            discord.ui.TextDisplay("## Download options"),
            discord.ui.Separator(),
            discord.ui.TextDisplay(
                "Pick a video quality or an audio format. Higher quality usually means a larger file."
            ),
            accent_colour=ACCENT,
        )
        video_row = discord.ui.ActionRow()
        for key in ("video_best", "video_1080", "video_720", "video_480", "video_360"):
            label = OPTIONS[key][0]
            button = discord.ui.Button(label=label, style=discord.ButtonStyle.secondary)
            async def callback(interaction: discord.Interaction, option=key):
                await self.start_download(interaction, option)
            button.callback = callback
            video_row.add_item(button)
        audio_row = discord.ui.ActionRow()
        for key in ("audio_mp3", "audio_m4a"):
            button = discord.ui.Button(label=OPTIONS[key][0], style=discord.ButtonStyle.primary)
            async def callback(interaction: discord.Interaction, option=key):
                await self.start_download(interaction, option)
            button.callback = callback
            audio_row.add_item(button)
        box.add_item(video_row)
        box.add_item(audio_row)
        self.add_item(box)

    async def start_download(self, interaction: discord.Interaction, option_key: str):
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message(
                "Run the command yourself to use these options.", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=self.ephemeral, thinking=True)
        label = OPTIONS[option_key][0]
        try:
            with tempfile.TemporaryDirectory(prefix="clipy_") as folder:
                path = await asyncio.wait_for(
                    asyncio.to_thread(download_sync, self.url, folder, option_key, self.max_bytes),
                    timeout=DOWNLOAD_TIMEOUT,
                )
                await interaction.followup.send(
                    content=f"{label} · {path.stat().st_size / (1024 * 1024):.1f} MB",
                    file=discord.File(path, filename=path.name),
                    ephemeral=self.ephemeral,
                )
        except asyncio.TimeoutError:
            await interaction.followup.send(
                "That download took too long. Try a lower quality.", ephemeral=self.ephemeral
            )
        except Exception as exc:
            log.info("Download failed (%s): %s", urlparse(self.url).hostname, type(exc).__name__)
            await interaction.followup.send(
                "Couldn't make that file. The video may be private, unavailable, or too large. "
                "Try a lower quality, or check that FFmpeg is installed for audio conversion.",
                ephemeral=self.ephemeral,
            )


class DownloadCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @staticmethod
    def upload_limit(guild: discord.Guild | None) -> int:
        # Discord reports the current guild's upload cap. Use a conservative fallback in DMs.
        return max(1, (getattr(guild, "filesize_limit", DEFAULT_MAX_BYTES) or DEFAULT_MAX_BYTES) - 512 * 1024)

    async def show_options(self, url: str, requester_id: int, guild: discord.Guild | None, send_view):
        safe_url = validate_url(url)
        if not safe_url:
            await send_view(error=True)
            return
        view = DownloadOptionsView(
            safe_url, requester_id, self.upload_limit(guild),
            ephemeral=guild is None,
        )
        await send_view(view=view)

    @app_commands.command(name="download", description="Choose a video quality or audio format.")
    @app_commands.describe(link="Public video URL from YouTube, Instagram, Facebook, or TikTok.")
    @app_commands.checks.cooldown(1, 20.0)
    async def slash_download(self, interaction: discord.Interaction, link: str):
        safe_url = validate_url(link)
        if not safe_url:
            await interaction.response.send_message(
                view=status_view("Unsupported link", "Use a public YouTube, Instagram, Facebook, or TikTok link."),
                ephemeral=True,
            )
            return
        view = DownloadOptionsView(
            safe_url, interaction.user.id, self.upload_limit(interaction.guild), ephemeral=True
        )
        await interaction.response.send_message(view=view, ephemeral=True)

    @commands.command(name="download")
    @commands.cooldown(1, 20.0, commands.BucketType.user)
    async def prefix_download(self, ctx: commands.Context, *, link: str):
        safe_url = validate_url(link)
        if not safe_url:
            await ctx.reply(
                view=status_view("Unsupported link", "Use a public YouTube, Instagram, Facebook, or TikTok link."),
                mention_author=False,
            )
            return
        view = DownloadOptionsView(
            safe_url, ctx.author.id, self.upload_limit(ctx.guild), ephemeral=False
        )
        await ctx.reply(view=view, mention_author=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(DownloadCommands(bot))
