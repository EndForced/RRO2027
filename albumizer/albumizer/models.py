"""Доменные модели. Не зависят ни от Telegram, ни от конкретных API."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


@dataclass(frozen=True)
class AlbumQuery:
    """Разобранный пользовательский запрос."""

    raw: str
    artist: str | None = None
    album: str | None = None

    @property
    def text(self) -> str:
        parts = [p for p in (self.artist, self.album) if p]
        return " ".join(parts) if parts else self.raw


@dataclass(frozen=True)
class Track:
    position: int
    title: str
    duration: float | None = None  # секунды
    artist: str | None = None  # если отличается от исполнителя альбома


@dataclass(frozen=True)
class AlbumCandidate:
    """Результат поиска метаданных — ещё без треклиста."""

    provider: str
    id: str
    artist: str
    title: str
    year: str | None = None
    track_count: int | None = None

    @property
    def label(self) -> str:
        year = f" ({self.year})" if self.year else ""
        count = f", {self.track_count} тр." if self.track_count else ""
        return f"{self.artist} — {self.title}{year}{count}"


@dataclass(frozen=True)
class Album:
    artist: str
    title: str
    tracks: tuple[Track, ...]
    year: str | None = None
    cover_url: str | None = None
    source: str | None = None  # провайдер метаданных

    @property
    def total_duration(self) -> float | None:
        if not self.tracks or any(t.duration is None for t in self.tracks):
            return None
        return sum(t.duration for t in self.tracks)  # type: ignore[misc]


class SourceKind(Enum):
    FULL_ALBUM = "full_album"  # один файл, нужно резать на треки
    TRACKS = "tracks"  # по ссылке на каждый трек


@dataclass(frozen=True)
class MediaRef:
    """Ссылка на медиа на какой-либо площадке."""

    url: str
    title: str
    duration: float | None = None
    uploader: str | None = None
    track: Track | None = None  # к какому треку альбома относится


@dataclass(frozen=True)
class SourceMatch:
    kind: SourceKind
    provider: str
    items: tuple[MediaRef, ...]
    score: float = 0.0

    @property
    def description(self) -> str:
        if self.kind is SourceKind.FULL_ALBUM:
            return f"{self.provider}: полный альбом — {self.items[0].title}"
        return f"{self.provider}: {len(self.items)} отдельных треков"


@dataclass(frozen=True)
class Chapter:
    title: str
    start: float
    end: float


@dataclass(frozen=True)
class DownloadedMedia:
    path: Path
    duration: float | None = None
    chapters: tuple[Chapter, ...] = ()


@dataclass(frozen=True)
class AudioFile:
    path: Path
    track: Track


@dataclass
class AlbumResult:
    album: Album
    source: SourceMatch
    files: list[AudioFile] = field(default_factory=list)
    workdir: Path | None = None  # временная папка задания, удаляется после отправки
