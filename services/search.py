"""YouTube search adapter using yt-dlp; it never downloads media."""
from __future__ import annotations
import asyncio
from dataclasses import dataclass
from typing import Any
from yt_dlp import YoutubeDL

@dataclass(slots=True)
class ClipResult:
    title: str
    url: str
    channel: str = "Unknown channel"
    duration: int | None = None
    source: str = "YouTube"

def _search_sync(query: str, limit: int) -> list[ClipResult]:
    opts: dict[str, Any] = {"quiet": True, "no_warnings": True, "skip_download": True, "extract_flat": True, "ignoreerrors": True, "socket_timeout": 12}
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
    results = []
    for item in (info or {}).get("entries") or []:
        if not item:
            continue
        video_id = item.get("id")
        url = item.get("webpage_url") or (f"https://www.youtube.com/watch?v={video_id}" if video_id else None)
        if url:
            results.append(ClipResult(item.get("title") or "Untitled video", url, item.get("channel") or item.get("uploader") or "Unknown channel", item.get("duration")))
    return results

async def search_youtube(query: str, limit: int = 9) -> list[ClipResult]:
    """Search YouTube off the event loop, with a hard timeout."""
    return await asyncio.wait_for(asyncio.to_thread(_search_sync, query, max(1, min(limit, 10))), timeout=25)
