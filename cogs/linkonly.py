"""Link-only channel moderation for Clipy."""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

import discord
from discord import app_commands
from discord.ext import commands

from utils.components import status_view

log = logging.getLogger(__name__)

STORE = Path(os.getenv("LINKONLY_STORE", "data/linkonly_channels.json"))
URL_PATTERN = re.compile(r"https?://[^\s<>]+", re.IGNORECASE)


def is_single_http_url(content: str) -> bool:
    """Return True only when the entire message is one syntactically valid HTTP(S) URL."""
    value = content.strip()
    if not value or not URL_PATTERN.fullmatch(value):
        return False
    try:
        parsed = urlsplit(value)
        _ = parsed.port
    except ValueError:
        return False
    return parsed.scheme.lower() in {"http", "https"} and bool(parsed.hostname)


class LinkOnly(commands.Cog):
    """Configure channels where members may post only a single URL."""

    linkonly = app_commands.Group(
        name="linkonly",
        description="Manage channels that only allow standalone links.",
    )

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.channels: dict[str, set[int]] = {}
        self._load()

    def _load(self) -> None:
        try:
            if not STORE.exists():
                return
            raw = json.loads(STORE.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("Expected a JSON object")
            for guild_id, channel_ids in raw.items():
                if isinstance(guild_id, str) and isinstance(channel_ids, list):
                    self.channels[guild_id] = {
                        int(channel_id)
                        for channel_id in channel_ids
                        if str(channel_id).isdigit()
                    }
        except (OSError, json.JSONDecodeError, ValueError):
            log.exception("Could not load link-only settings from %s", STORE)

    def _save(self) -> None:
        STORE.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            guild_id: sorted(channel_ids)
            for guild_id, channel_ids in sorted(self.channels.items())
            if channel_ids
        }
        temporary = STORE.with_suffix(STORE.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(STORE)

    def _enabled(self, guild_id: int, channel_id: int) -> bool:
        return channel_id in self.channels.get(str(guild_id), set())

    async def _set_channel(
        self,
        guild: discord.Guild,
        channel: discord.TextChannel,
        enabled: bool,
    ) -> tuple[bool, str]:
        bot_member = guild.me
        if enabled and (bot_member is None or not channel.permissions_for(bot_member).manage_messages):
            return False, f"I need **Manage Messages** in {channel.mention} to enforce link-only mode."

        guild_key = str(guild.id)
        channel_ids = self.channels.setdefault(guild_key, set())
        was_enabled = channel.id in channel_ids
        if enabled:
            if was_enabled:
                return True, f"Link-only mode is already enabled in {channel.mention}."
            channel_ids.add(channel.id)
        else:
            if not was_enabled:
                return True, f"Link-only mode is not enabled in {channel.mention}."
            channel_ids.remove(channel.id)
            if not channel_ids:
                self.channels.pop(guild_key, None)

        try:
            self._save()
        except OSError:
            if enabled:
                self.channels.get(guild_key, set()).discard(channel.id)
                if not self.channels.get(guild_key):
                    self.channels.pop(guild_key, None)
            else:
                self.channels.setdefault(guild_key, set()).add(channel.id)
            log.exception("Could not save link-only settings")
            return False, "I couldn't save the settings. Check the bot host's file permissions and try again."

        action = "enabled" if enabled else "disabled"
        return True, f"Link-only mode **{action}** in {channel.mention}."

    @linkonly.command(name="set", description="Allow only standalone URLs in a channel.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(channel="The text channel to restrict.")
    async def slash_set(self, interaction: discord.Interaction, channel: discord.TextChannel):
        _, message = await self._set_channel(interaction.guild, channel, True)
        await interaction.response.send_message(view=status_view("Link-only mode", message, ephemeral_colour=True), ephemeral=True)

    @linkonly.command(name="remove", description="Turn off link-only mode in a channel.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(channel="The text channel to unrestrict.")
    async def slash_remove(self, interaction: discord.Interaction, channel: discord.TextChannel):
        _, message = await self._set_channel(interaction.guild, channel, False)
        await interaction.response.send_message(view=status_view("Link-only mode", message, ephemeral_colour=True), ephemeral=True)

    @commands.group(name="linkonly", invoke_without_command=True)
    @commands.guild_only()
    async def prefix_linkonly(self, ctx: commands.Context):
        prefix = getattr(ctx.bot, "guild_prefixes", {}).get(
            str(ctx.guild.id), os.getenv("BOT_PREFIX", "!")
        )
        await ctx.send(view=status_view(
            "Link-only commands",
            f"Use `{prefix}linkonly set #channel` or `{prefix}linkonly remove #channel`. Requires **Manage Server** permission."
        ))

    @prefix_linkonly.command(name="set")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def prefix_set(self, ctx: commands.Context, channel: discord.TextChannel):
        _, message = await self._set_channel(ctx.guild, channel, True)
        await ctx.send(view=status_view("Link-only mode", message))

    @prefix_linkonly.command(name="remove")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def prefix_remove(self, ctx: commands.Context, channel: discord.TextChannel):
        _, message = await self._set_channel(ctx.guild, channel, False)
        await ctx.send(view=status_view("Link-only mode", message))

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is None or message.author.bot:
            return
        if not self._enabled(message.guild.id, message.channel.id):
            return
        if is_single_http_url(message.content) and not message.attachments and not message.stickers:
            return

        deleted = False
        try:
            await message.delete()
            deleted = True
        except discord.NotFound:
            deleted = True
        except discord.Forbidden:
            log.warning(
                "Cannot delete a non-link message in link-only channel %s (guild %s): missing Manage Messages",
                message.channel.id,
                message.guild.id,
            )
        except discord.HTTPException:
            log.exception("Failed to delete a message in link-only channel %s", message.channel.id)

        try:
            channel_name = getattr(message.channel, "name", "this channel")
            if deleted:
                warning = (
                    f"Your message in **#{channel_name}** was removed because the channel is link-only. "
                    "Send one valid HTTP(S) URL by itself, with no extra text."
                )
            else:
                warning = (
                    f"**#{channel_name}** only allows one valid HTTP(S) URL per message, with no extra text. "
                    "The bot could not remove your message because it lacks permission."
                )
            await message.author.send(view=status_view("Link-only notice", warning))
        except (discord.Forbidden, discord.HTTPException):
            log.info("Could not DM link-only warning to user %s", message.author.id)


async def setup(bot: commands.Bot):
    await bot.add_cog(LinkOnly(bot))
