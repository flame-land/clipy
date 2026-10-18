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
from yt_dlp.utils import download_range_func

from utils.components import ACCENT, status_view

log = logging.getLogger(__name__)
# Discord's DM attachment cap isn't exposed as consistently as a guild's cap.
# Keep a generous fallback, then enforce the known Discord cap when available.
DEFAULT_MAX_BYTES = 100 * 1024 * 1024
DOWNLOAD_TIMEOUT = 600
MAX_CLIP_SECONDS = 60
ALLOWED_HOSTS = {
    "youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "www.youtu.be",
    "instagram.com", "www.instagram.com",
    "facebook.com", "www.facebook.com", "m.facebook.com", "fb.watch",
    "tiktok.com", "www.tiktok.com", "m.tiktok.com", "vm.tiktok.com", "vt.tiktok.com",
    "vimeo.com", "www.vimeo.com", "player.vimeo.com",
    "reddit.com", "www.reddit.com", "old.reddit.com", "v.redd.it",
    "x.com", "www.x.com", "twitter.com", "www.twitter.com", "t.co",
    "dailymotion.com", "www.dailymotion.com", "dai.ly",
    "streamable.com", "www.streamable.com",
    "twitch.tv", "www.twitch.tv", "clips.twitch.tv",
    "pinterest.com", "www.pinterest.com", "pin.it",
    "tumblr.com", "www.tumblr.com",
}

VIDEO_QUALITIES = {
    "best": ("Best available", None),
    "1080": ("1080p", 1080),
    "720": ("720p", 720),
    "480": ("480p", 480),
    "360": ("360p", 360),
}
AUDIO_QUALITIES = {
    "128": "128 kbps",
    "192": "192 kbps",
    "320": "320 kbps",
}
VIDEO_FORMATS = {"mp4": "MP4", "webm": "WebM"}
AUDIO_FORMATS = {"mp3": "MP3", "m4a": "M4A"}


def validate_url(url: str) -> str | None:
    """Accept only HTTPS links on the explicit allowlist; reject credentials and custom ports."""
    candidate = url.strip()
    try:
        parsed = urlparse(candidate)
        host = (parsed.hostname or "").lower().rstrip(".")
        # Avoid userinfo tricks, custom ports, non-HTTPS URLs, and unapproved hosts.
        if parsed.scheme.lower() != "https" or not host:
            return None
        if parsed.username is not None or parsed.password is not None:
            return None
        if parsed.port not in (None, 443):
            return None
        if host not in ALLOWED_HOSTS:
            return None
        return candidate
    except ValueError:
        # urlparse can raise for malformed bracketed hosts or ports.
        return None


def download_sync(
    url: str,
    folder: str,
    mode: str,
    quality: str,
    file_format: str,
    max_bytes: int,
) -> Path:
    output = str(Path(folder) / "clip.%(ext)s")
    opts = {
        "outtmpl": output,
        "max_filesize": max_bytes,
        "noplaylist": True,
        "max_downloads": 1,
        "cachedir": False,
        "writeinfojson": False,
        "writethumbnail": False,
        "writesubtitles": False,
        "writeautomaticsub": False,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 20,
        "retries": 2,
        "overwrites": True,
        # Download/process only the first 60 seconds; requires FFmpeg.
        "download_ranges": download_range_func(None, [(0, MAX_CLIP_SECONDS)]),
        "force_keyframes_at_cuts": True,
    }

    if mode == "video":
        height = VIDEO_QUALITIES[quality][1]
        cap = f"[height<={height}]" if height else ""
        if file_format == "mp4":
            opts["format"] = (
                f"bestvideo[ext=mp4]{cap}+bestaudio[ext=m4a]/"
                f"best[ext=mp4]{cap}/best{cap}/best"
            )
        else:
            opts["format"] = (
                f"bestvideo[ext=webm]{cap}+bestaudio[ext=webm]/"
                f"best[ext=webm]{cap}/best{cap}/best"
            )
        opts["merge_output_format"] = file_format
    else:
        opts["format"] = "bestaudio/best"
        if file_format == "mp3":
            opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": quality,
            }]
        else:
            # M4A is copied when the source is already compatible.
            opts["format"] = "bestaudio[ext=m4a]/bestaudio/best"
            opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "m4a",
                "preferredquality": quality,
            }]

    with YoutubeDL(opts) as ydl:
        ydl.download([url])

    files = [
        p for p in Path(folder).iterdir()
        if p.is_file() and not p.name.endswith((".part", ".ytdl"))
    ]
    if not files:
        raise RuntimeError("No file was produced.")
    file_path = max(files, key=lambda p: p.stat().st_size)
    if file_path.stat().st_size > max_bytes:
        file_path.unlink(missing_ok=True)
        raise ValueError("The finished file exceeds this server's upload limit.")
    return file_path


class DownloadOptionsView(discord.ui.LayoutView):
    def __init__(self, url: str, requester_id: int, max_bytes: int, *, ephemeral: bool):
        super().__init__(timeout=300)
        self.url = url
        self.requester_id = requester_id
        self.max_bytes = max_bytes
        self.ephemeral = ephemeral
        self.mode = "video"
        self.video_quality = "720"
        self.video_format = "mp4"
        self.audio_quality = "192"
        self.audio_format = "mp3"
        self.render()

    def render(self):
        self.clear_items()
        mode_options = [
            discord.SelectOption(label="Video", value="video", default=self.mode == "video"),
            discord.SelectOption(label="Audio", value="audio", default=self.mode == "audio"),
        ]
        mode_select = discord.ui.Select(
            placeholder="What do you want to download?",
            options=mode_options,
            min_values=1,
            max_values=1,
        )

        async def choose_mode(interaction: discord.Interaction):
            if not await self.check_requester(interaction):
                return
            self.mode = mode_select.values[0]
            self.render()
            await interaction.response.edit_message(view=self)

        mode_select.callback = choose_mode

        if self.mode == "video":
            quality_options = [
                discord.SelectOption(label=label, value=value, default=value == self.video_quality)
                for value, (label, _) in VIDEO_QUALITIES.items()
            ]
            format_options = [
                discord.SelectOption(label=label, value=value, default=value == self.video_format)
                for value, label in VIDEO_FORMATS.items()
            ]
            quality_placeholder = "Video quality"
            format_placeholder = "Video format"
        else:
            quality_options = [
                discord.SelectOption(label=label, value=value, default=value == self.audio_quality)
                for value, label in AUDIO_QUALITIES.items()
            ]
            format_options = [
                discord.SelectOption(label=label, value=value, default=value == self.audio_format)
                for value, label in AUDIO_FORMATS.items()
            ]
            quality_placeholder = "Audio quality"
            format_placeholder = "Audio format"

        quality_select = discord.ui.Select(
            placeholder=quality_placeholder,
            options=quality_options,
            min_values=1,
            max_values=1,
        )
        format_select = discord.ui.Select(
            placeholder=format_placeholder,
            options=format_options,
            min_values=1,
            max_values=1,
        )

        async def choose_quality(interaction: discord.Interaction):
            if not await self.check_requester(interaction):
                return
            if self.mode == "video":
                self.video_quality = quality_select.values[0]
            else:
                self.audio_quality = quality_select.values[0]
            self.render()
            await interaction.response.edit_message(view=self)

        async def choose_format(interaction: discord.Interaction):
            if not await self.check_requester(interaction):
                return
            if self.mode == "video":
                self.video_format = format_select.values[0]
            else:
                self.audio_format = format_select.values[0]
            self.render()
            await interaction.response.edit_message(view=self)

        quality_select.callback = choose_quality
        format_select.callback = choose_format

        async def download_button(interaction: discord.Interaction):
            if self.mode == "video":
                await self.start_download(interaction, "video", self.video_quality, self.video_format)
            else:
                await self.start_download(interaction, "audio", self.audio_quality, self.audio_format)

        button = discord.ui.Button(label="Download", style=discord.ButtonStyle.primary)
        button.callback = download_button

        box = discord.ui.Container(
            discord.ui.TextDisplay("## Download"),
            discord.ui.Separator(),
            discord.ui.TextDisplay(
                "Choose a type, quality, and format. Bigger files may need a lower quality to fit Discord."
            ),
            discord.ui.ActionRow(mode_select),
            discord.ui.ActionRow(quality_select),
            discord.ui.ActionRow(format_select),
            discord.ui.ActionRow(button),
            accent_colour=ACCENT,
        )
        self.add_item(box)

    async def check_requester(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message(
                "Run the command yourself to use these options.", ephemeral=True
            )
            return False
        return True

    async def start_download(
        self,
        interaction: discord.Interaction,
        mode: str,
        quality: str,
        file_format: str,
    ):
        if not await self.check_requester(interaction):
            return
        await interaction.response.defer(ephemeral=self.ephemeral, thinking=True)
        if mode == "video":
            label = f"Video · {VIDEO_QUALITIES[quality][0]} · {VIDEO_FORMATS[file_format]}"
        else:
            label = f"Audio · {AUDIO_FORMATS[file_format]} · {AUDIO_QUALITIES[quality]}"
        try:
            with tempfile.TemporaryDirectory(prefix="clipy_") as folder:
                path = await asyncio.wait_for(
                    asyncio.to_thread(
                        download_sync, self.url, folder, mode, quality, file_format, self.max_bytes
                    ),
                    timeout=DOWNLOAD_TIMEOUT,
                )
                size_mb = path.stat().st_size / (1024 * 1024)
                await interaction.followup.send(
                    content=f"{label} · {size_mb:.1f} MB",
                    file=discord.File(path, filename=path.name),
                    ephemeral=self.ephemeral,
                )
        except asyncio.TimeoutError:
            await interaction.followup.send(
                "That took too long. Try a lower quality or a shorter clip.",
                ephemeral=self.ephemeral,
            )
        except Exception as exc:
            log.info("Download failed (%s): %s", urlparse(self.url).hostname, type(exc).__name__)
            await interaction.followup.send(
                "Couldn't make that file. It may be unavailable, too large for Discord, or need FFmpeg. "
                "Try a lower quality or another format.",
                ephemeral=self.ephemeral,
            )


class DownloadCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @staticmethod
    def upload_limit(guild: discord.Guild | None) -> int:
        # Respect the server's real attachment limit when Discord exposes it.
        limit = getattr(guild, "filesize_limit", None) if guild else None
        return max(1, (limit or DEFAULT_MAX_BYTES) - 512 * 1024)

    @app_commands.command(name="download", description="Choose download type, quality, and format.")
    @app_commands.describe(link="Public clip URL from a supported video platform. Only the first 60 seconds are downloaded.")
    @app_commands.checks.cooldown(1, 20.0)
    async def slash_download(self, interaction: discord.Interaction, link: str):
        safe_url = validate_url(link)
        if not safe_url:
            await interaction.response.send_message(
                view=status_view("Unsupported link", "Use a public clip link from a supported video platform."),
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
