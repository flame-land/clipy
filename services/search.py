"""YouTube search adapter using yt-dlp; returns mixed-length results with thumbnails."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from yt_dlp import YoutubeDL


MAX_SEARCH_RESULTS = 60


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
    # Search a broad pool so filtering duplicates or incomplete entries still
    # leaves enough results to show the requested number to the user.
    candidate_count = min(max(limit * 5, 30), MAX_SEARCH_RESULTS)
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"ytsearch{candidate_count}:{query}", download=False)

    results: list[ClipResult] = []
    seen: set[str] = set()
    for item in (info or {}).get("entries") or []:
        if not item:
            continue
        video_id = item.get("id")
        url = item.get("webpage_url") or (f"https://www.youtube.com/watch?v={video_id}" if video_id else None)
        if not url or url in seen:
            continue
        seen.add(url)
        raw_duration = item.get("duration")
        try:
            duration = int(raw_duration) if raw_duration is not None and raw_duration >= 0 else None
        except (TypeError, ValueError):
            duration = None
        results.append(ClipResult(
            title=item.get("title") or "Untitled video",
            url=url,
            channel=item.get("channel") or item.get("uploader") or "Unknown channel",
            duration=duration,
            source=item.get("extractor_key") or "YouTube",
            thumbnail=item.get("thumbnail"),
        ))
        if len(results) >= limit:
            break
    return results


async def search_youtube(query: str, limit: int = 9) -> list[ClipResult]:
    """Return up to nine YouTube results of any duration, including unknown durations."""
    safe_limit = max(1, min(limit, 9))
    return await asyncio.wait_for(
        asyncio.to_thread(_search_sync, query, safe_limit),
        timeout=35,
    )
