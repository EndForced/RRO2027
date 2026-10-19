"""Контракты между слоями. Пайплайн и бот знают только про эти протоколы."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

from .models import (
    Album,
    AlbumCandidate,
    AlbumQuery,
    AlbumResult,
    AudioFile,
    DownloadedMedia,
    MediaRef,
    SourceMatch,
)


class LLMClient(Protocol):
    async def complete(self, system: str, user: str) -> str: ...


class QueryParser(Protocol):
    async def parse(self, text: str) -> AlbumQuery: ...


class MetadataProvider(Protocol):
    name: str

    async def search(self, query: AlbumQuery, limit: int = 5) -> list[AlbumCandidate]: ...

    async def get_album(self, candidate: AlbumCandidate) -> Album: ...


class MediaSearcher(Protocol):
    """Низкоуровневый поиск на площадке (YouTube, SoundCloud...)."""

    name: str

    async def search(self, query: str, limit: int = 10) -> list[MediaRef]: ...


class PlaylistExtractor(Protocol):
    """Достаёт список треков по ссылке на альбом/плейлист."""

    async def extract(self, url: str) -> list[MediaRef]: ...


class SourceFinder(Protocol):
    """Стратегия поиска источника для всего альбома."""

    name: str

    async def find(self, album: Album) -> SourceMatch | None: ...


class SourceJudge(Protocol):
    """Опциональная проверка (например, через LLM), что видео — нужный альбом."""

    async def is_full_album(self, album: Album, ref: MediaRef) -> bool: ...


class Downloader(Protocol):
    async def download(self, ref: MediaRef, dest_dir: Path) -> DownloadedMedia: ...


class AudioSplitter(Protocol):
    async def split(self, media: DownloadedMedia, album: Album, dest_dir: Path) -> list[AudioFile]: ...


class Tagger(Protocol):
    async def tag(self, files: list[AudioFile], album: Album, cover: bytes | None) -> None: ...


class CoverLoader(Protocol):
    async def load(self, url: str) -> bytes | None: ...


class ProgressReporter(Protocol):
    async def __call__(self, message: str) -> None: ...


class AlbumService(Protocol):
    """Фасад пайплайна — единственное, что знает бот."""

    async def search(self, text: str, limit: int = 6) -> list[AlbumCandidate]: ...

    async def load_album(self, candidate: AlbumCandidate) -> Album: ...

    async def find_source(self, album: Album) -> SourceMatch | None: ...

    async def build(
        self, album: Album, source: SourceMatch, progress: ProgressReporter | None = None
    ) -> AlbumResult: ...

    def cleanup(self, result: AlbumResult) -> None: ...
