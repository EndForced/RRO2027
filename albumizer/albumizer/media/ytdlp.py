"""Адаптеры yt-dlp: поиск, извлечение плейлистов, скачивание.

yt-dlp синхронный, поэтому все вызовы уходят в отдельный поток.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import yt_dlp

from ..models import Chapter, DownloadedMedia, MediaRef

log = logging.getLogger(__name__)

_BASE_OPTS: dict[str, Any] = {
    "quiet": True,
    "no_warnings": True,
    "noprogress": True,
    "ignoreerrors": "only_download",
}


def _ref(entry: dict[str, Any]) -> MediaRef | None:
    url = entry.get("webpage_url") or entry.get("url")
    if not url:
        return None
    return MediaRef(
        url=url,
        title=entry.get("title") or "",
        duration=float(entry["duration"]) if entry.get("duration") else None,
        uploader=entry.get("channel") or entry.get("uploader") or entry.get("artist"),
    )


class YtDlpSearcher:
    """Поиск через yt-dlp.

    `template` — либо поисковый префикс ("ytsearch{limit}:{query}", "scsearch{limit}:{query}"),
    либо URL ("https://music.youtube.com/search?q={query}#albums").
    """

    def __init__(
        self,
        name: str,
        template: str,
        *,
        flat: bool = True,
        extra_opts: dict[str, Any] | None = None,
    ) -> None:
        self.name = name
        self._template = template
        self._is_url = template.startswith("http")
        self._opts = {**_BASE_OPTS, **(extra_opts or {})}
        if flat:
            self._opts["extract_flat"] = "in_playlist"

    async def search(self, query: str, limit: int = 10) -> list[MediaRef]:
        q = quote_plus(query) if self._is_url else query
        url = self._template.format(query=q, limit=limit)
        opts = {**self._opts, "playlistend": limit}
        info = await asyncio.to_thread(_extract, url, opts)
        refs = [_ref(e) for e in (info or {}).get("entries") or [] if e]
        return [r for r in refs if r][:limit]


class YtDlpPlaylistExtractor:
    """Достаёт треки альбома/плейлиста (YouTube Music, Bandcamp, SoundCloud sets...)."""

    def __init__(self, *, flat: bool = True, extra_opts: dict[str, Any] | None = None) -> None:
        self._opts = {**_BASE_OPTS, **(extra_opts or {})}
        if flat:
            self._opts["extract_flat"] = "in_playlist"

    async def extract(self, url: str) -> list[MediaRef]:
        info = await asyncio.to_thread(_extract, url, self._opts)
        if not info:
            return []
        entries = info.get("entries")
        if entries is None:  # одиночный трек, а не плейлист
            ref = _ref(info)
            return [ref] if ref else []
        return [r for r in (_ref(e) for e in entries if e) if r]


class YtDlpDownloader:
    def __init__(
        self,
        *,
        audio_format: str = "mp3",
        audio_quality: str = "192",
        extra_opts: dict[str, Any] | None = None,
    ) -> None:
        self._format = audio_format
        self._quality = audio_quality
        self._extra = extra_opts or {}

    async def download(self, ref: MediaRef, dest_dir: Path) -> DownloadedMedia:
        dest_dir.mkdir(parents=True, exist_ok=True)
        opts = {
            **_BASE_OPTS,
            "ignoreerrors": False,
            "format": "bestaudio/best",
            "noplaylist": True,
            "outtmpl": str(dest_dir / "%(id)s.%(ext)s"),
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": self._format,
                    "preferredquality": self._quality,
                }
            ],
            **self._extra,
        }
        return await asyncio.to_thread(self._download_sync, ref.url, opts, dest_dir)

    def _download_sync(self, url: str, opts: dict[str, Any], dest_dir: Path) -> DownloadedMedia:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info is None:
                raise RuntimeError(f"yt-dlp returned nothing for {url}")
            path = Path(ydl.prepare_filename(info)).with_suffix(f".{self._format}")
        if not path.exists():  # подстраховка на случай нестандартного имени
            matches = sorted(dest_dir.glob(f"{info.get('id', '*')}.{self._format}"))
            if not matches:
                raise FileNotFoundError(f"downloaded file not found for {url}")
            path = matches[0]
        chapters = tuple(
            Chapter(title=c.get("title") or "", start=float(c["start_time"]), end=float(c["end_time"]))
            for c in info.get("chapters") or []
            if c.get("start_time") is not None and c.get("end_time") is not None
        )
        duration = float(info["duration"]) if info.get("duration") else None
        return DownloadedMedia(path=path, duration=duration, chapters=chapters)


def _extract(url: str, opts: dict[str, Any]) -> dict[str, Any] | None:
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as exc:
        log.warning("yt-dlp failed for %s: %s", url, exc)
        return None
