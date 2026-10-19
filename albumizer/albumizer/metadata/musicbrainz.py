"""MusicBrainz: открытая база, без ключа, лимит 1 запрос/сек, нужен User-Agent."""
from __future__ import annotations

import asyncio
import time

import httpx

from ..models import Album, AlbumCandidate, AlbumQuery, Track


class MusicBrainzMetadata:
    name = "musicbrainz"
    BASE = "https://musicbrainz.org/ws/2"
    COVER = "https://coverartarchive.org/release/{id}/front-500"

    def __init__(self, client: httpx.AsyncClient, user_agent: str, min_interval: float = 1.0) -> None:
        self._client = client
        self._headers = {"User-Agent": user_agent, "Accept": "application/json"}
        self._min_interval = min_interval
        self._lock = asyncio.Lock()
        self._last_call = 0.0

    async def _get(self, path: str, params: dict) -> dict:
        async with self._lock:  # соблюдаем rate limit MusicBrainz
            wait = self._min_interval - (time.monotonic() - self._last_call)
            if wait > 0:
                await asyncio.sleep(wait)
            try:
                resp = await self._client.get(
                    f"{self.BASE}/{path}", params={**params, "fmt": "json"}, headers=self._headers
                )
            finally:
                self._last_call = time.monotonic()
        resp.raise_for_status()
        return resp.json()

    async def search(self, query: AlbumQuery, limit: int = 5) -> list[AlbumCandidate]:
        if query.artist and query.album:
            lucene = f'release:"{_esc(query.album)}" AND artist:"{_esc(query.artist)}"'
        else:
            lucene = _esc(query.text)
        data = await self._get("release", {"query": lucene, "limit": limit * 3})
        seen: set[tuple[str, str, int | None]] = set()
        result: list[AlbumCandidate] = []
        for rel in data.get("releases", []):
            artist = _credit(rel.get("artist-credit", []))
            key = (artist.lower(), rel.get("title", "").lower(), rel.get("track-count"))
            if key in seen:  # у альбома десятки изданий — показываем одно
                continue
            seen.add(key)
            result.append(
                AlbumCandidate(
                    provider=self.name,
                    id=rel["id"],
                    artist=artist,
                    title=rel.get("title", "?"),
                    year=(rel.get("date") or "")[:4] or None,
                    track_count=rel.get("track-count"),
                )
            )
            if len(result) >= limit:
                break
        return result

    async def get_album(self, candidate: AlbumCandidate) -> Album:
        data = await self._get(f"release/{candidate.id}", {"inc": "recordings artist-credits"})
        album_artist = _credit(data.get("artist-credit", [])) or candidate.artist
        tracks: list[Track] = []
        for medium in data.get("media", []):
            for t in medium.get("tracks", []):
                length = t.get("length") or (t.get("recording") or {}).get("length")
                artist = _credit(t.get("artist-credit", []))
                tracks.append(
                    Track(
                        position=len(tracks) + 1,
                        title=t.get("title", f"Track {len(tracks) + 1}"),
                        duration=length / 1000 if length else None,
                        artist=artist if artist and artist != album_artist else None,
                    )
                )
        has_cover = (data.get("cover-art-archive") or {}).get("front")
        return Album(
            artist=album_artist,
            title=data.get("title", candidate.title),
            tracks=tuple(tracks),
            year=(data.get("date") or "")[:4] or candidate.year,
            cover_url=self.COVER.format(id=candidate.id) if has_cover else None,
            source=self.name,
        )


def _credit(credits: list[dict]) -> str:
    return "".join(f"{c.get('name', '')}{c.get('joinphrase', '')}" for c in credits).strip()


def _esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')
