"""YouTube search adapter using yt-dlp; returns short clips with preview thumbnails."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from yt_dlp import YoutubeDL


MAX_CLIP_SECONDS = 60


@dataclass(slots=True)
class ClipResult:
    title: str
    url: str
    channel: str = "Unknown channel"
    duration: int | None = None
    source: str = "YouTube"
    thumbnail: str | None = None


def _search_sync(query: str, limit: int) -> list[ClipResult]:
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": True,
        "ignoreerrors": True,
        "socket_timeout": 12,
    }
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"ytsearch{min(limit * 3, 30)}:{query}", download=False)

    results: list[ClipResult] = []
    seen: set[str] = set()
    for item in (info or {}).get("entries") or []:
        if not item:
            continue
        duration = item.get("duration")
        # Only show known-duration clips no longer than one minute.
        if duration is None or duration < 0 or duration > MAX_CLIP_SECONDS:
            continue
        video_id = item.get("id")
        url = item.get("webpage_url") or (f"https://www.youtube.com/watch?v={video_id}" if video_id else None)
        if not url or url in seen:
            continue
        seen.add(url)
        results.append(ClipResult(
            title=item.get("title") or "Untitled video",
            url=url,
            channel=item.get("channel") or item.get("uploader") or "Unknown channel",
            duration=int(duration),
            source=item.get("extractor_key") or "YouTube",
            thumbnail=item.get("thumbnail"),
        ))
        if len(results) >= limit:
            break
    return results


async def search_youtube(query: str, limit: int = 9) -> list[ClipResult]:
    """Search YouTube off the event loop with a hard timeout, returning clips up to 60 seconds."""
    return await asyncio.wait_for(
        asyncio.to_thread(_search_sync, query, max(1, min(limit, 10))),
        timeout=25,
    )
