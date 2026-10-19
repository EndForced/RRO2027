"""Deezer public API: без ключа, быстрый, есть длительности и обложки."""
from __future__ import annotations

import httpx

from ..models import Album, AlbumCandidate, AlbumQuery, Track


class DeezerMetadata:
    name = "deezer"
    BASE = "https://api.deezer.com"

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def search(self, query: AlbumQuery, limit: int = 5) -> list[AlbumCandidate]:
        if query.artist and query.album:
            q = f'artist:"{query.artist}" album:"{query.album}"'
        else:
            q = query.text
        resp = await self._client.get(f"{self.BASE}/search/album", params={"q": q, "limit": limit})
        resp.raise_for_status()
        return [
            AlbumCandidate(
                provider=self.name,
                id=str(item["id"]),
                artist=item.get("artist", {}).get("name", "?"),
                title=item.get("title", "?"),
                track_count=item.get("nb_tracks"),
            )
            for item in resp.json().get("data", [])
        ]

    async def get_album(self, candidate: AlbumCandidate) -> Album:
        resp = await self._client.get(f"{self.BASE}/album/{candidate.id}")
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise LookupError(f"deezer: {data['error']}")
        album_artist = data.get("artist", {}).get("name", candidate.artist)
        tracks = tuple(
            Track(
                position=i,
                title=t.get("title", f"Track {i}"),
                duration=float(t["duration"]) if t.get("duration") else None,
                artist=_other(t.get("artist", {}).get("name"), album_artist),
            )
            for i, t in enumerate(data.get("tracks", {}).get("data", []), start=1)
        )
        return Album(
            artist=album_artist,
            title=data.get("title", candidate.title),
            tracks=tracks,
            year=(data.get("release_date") or "")[:4] or None,
            cover_url=data.get("cover_xl") or data.get("cover_big"),
            source=self.name,
        )


def _other(name: str | None, album_artist: str) -> str | None:
    return name if name and name != album_artist else None
