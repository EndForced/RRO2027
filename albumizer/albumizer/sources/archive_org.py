"""Internet Archive: открытый API поиска и метаданных, файлы качаются напрямую."""
from __future__ import annotations

import re
from urllib.parse import quote

import httpx

from ..models import MediaRef

_AUDIO_FORMATS = ("VBR MP3", "320Kbps MP3", "256Kbps MP3", "MP3", "128Kbps MP3", "Ogg Vorbis", "Flac")


class ArchiveOrgSearcher:
    name = "archive_org"
    URL = "https://archive.org/advancedsearch.php"

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def search(self, query: str, limit: int = 10) -> list[MediaRef]:
        params = [
            ("q", f"({query}) AND mediatype:(audio)"),
            ("fl[]", "identifier"),
            ("fl[]", "title"),
            ("fl[]", "creator"),
            ("rows", str(limit)),
            ("output", "json"),
        ]
        resp = await self._client.get(self.URL, params=params)
        resp.raise_for_status()
        refs = []
        for doc in resp.json().get("response", {}).get("docs", []):
            creator = doc.get("creator")
            if isinstance(creator, list):
                creator = ", ".join(creator)
            refs.append(
                MediaRef(
                    url=f"https://archive.org/details/{doc['identifier']}",
                    title=_first(doc.get("title")) or doc["identifier"],
                    uploader=creator,
                )
            )
        return refs


class ArchiveOrgExtractor:
    """Список аудиофайлов элемента архива в порядке треков."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def extract(self, url: str) -> list[MediaRef]:
        identifier = url.rstrip("/").rsplit("/", 1)[-1]
        resp = await self._client.get(f"https://archive.org/metadata/{identifier}")
        resp.raise_for_status()
        return parse_metadata(identifier, resp.json())


def parse_metadata(identifier: str, data: dict) -> list[MediaRef]:
    files = data.get("files", [])
    for fmt in _AUDIO_FORMATS:  # берём лучший доступный формат, а не все копии сразу
        chosen = [f for f in files if f.get("format") == fmt]
        if chosen:
            break
    else:
        return []
    chosen.sort(key=lambda f: (_track_no(f.get("track")), f.get("name", "")))
    return [
        MediaRef(
            url=f"https://archive.org/download/{identifier}/{quote(f['name'])}",
            title=f.get("title") or _stem(f["name"]),
            duration=_length(f.get("length")),
            uploader=f.get("creator") or f.get("artist"),
        )
        for f in chosen
    ]


def _first(value: str | list | None) -> str | None:
    return value[0] if isinstance(value, list) and value else value  # type: ignore[return-value]


def _track_no(value: str | None) -> int:
    match = re.match(r"\d+", value or "")
    return int(match.group()) if match else 10_000


def _length(value: str | None) -> float | None:
    if not value:
        return None
    try:
        if ":" in value:
            secs = 0.0
            for part in value.split(":"):
                secs = secs * 60 + float(part)
            return secs
        return float(value)
    except ValueError:
        return None


def _stem(name: str) -> str:
    stem = name.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    return re.sub(r"^\d+[\s._-]*", "", stem)
