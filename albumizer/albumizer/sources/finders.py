"""Стратегии поиска источника альбома. Каждая работает с абстрактными
MediaSearcher/PlaylistExtractor, поэтому одна стратегия обслуживает разные площадки."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence

from ..interfaces import MediaSearcher, PlaylistExtractor, SourceFinder, SourceJudge
from ..matching import (
    duration_matches,
    duration_score,
    duration_tolerance,
    has_negative_words,
    title_similarity,
)
from ..models import Album, MediaRef, SourceKind, SourceMatch, Track

log = logging.getLogger(__name__)


class FullAlbumVideoFinder:
    """Одно видео со всем альбомом: ищем по запросам, сверяем длину с суммой треков."""

    DEFAULT_QUERIES = ("{artist} {album} full album", "{artist} {album} album")

    def __init__(
        self,
        searcher: MediaSearcher,
        *,
        name: str | None = None,
        judge: SourceJudge | None = None,
        queries: Sequence[str] = DEFAULT_QUERIES,
        tolerance_abs: float = 45.0,
        tolerance_rel: float = 0.03,
        min_title_score: float = 0.6,
        results_per_query: int = 15,
    ) -> None:
        self.name = name or f"{searcher.name}_full"
        self._searcher = searcher
        self._judge = judge
        self._queries = queries
        self._tol_abs, self._tol_rel = tolerance_abs, tolerance_rel
        self._min_title = min_title_score
        self._per_query = results_per_query

    async def find(self, album: Album) -> SourceMatch | None:
        expected = album.total_duration
        if expected is None:
            return None  # без длительностей не можем проверить и нарезать
        tolerance = duration_tolerance(expected, absolute=self._tol_abs, relative=self._tol_rel)
        reference = f"{album.artist} {album.title}"

        scored: dict[str, tuple[float, MediaRef]] = {}
        for template in self._queries:
            query = template.format(artist=album.artist, album=album.title)
            for ref in await self._searcher.search(query, self._per_query):
                if ref.url in scored or not duration_matches(
                    ref.duration, expected, absolute=self._tol_abs, relative=self._tol_rel
                ):
                    continue
                if has_negative_words(ref.title, reference):
                    continue
                haystack = f"{ref.uploader or ''} {ref.title}"
                t_score = min(
                    title_similarity(album.title, ref.title),
                    title_similarity(album.artist, haystack),
                )
                if t_score < self._min_title:
                    continue
                d_score = duration_score(ref.duration, expected, tolerance)
                scored[ref.url] = (0.6 * t_score + 0.4 * d_score, ref)

        for score, ref in sorted(scored.values(), key=lambda x: x[0], reverse=True):
            if self._judge and not await self._judge.is_full_album(album, ref):
                log.info("judge rejected %s", ref.title)
                continue
            return SourceMatch(SourceKind.FULL_ALBUM, self.name, (ref,), score)
        return None


class PlaylistAlbumFinder:
    """Альбом как плейлист на площадке (YouTube Music, Bandcamp, Archive.org):
    находим страницу альбома и сопоставляем её треки с треклистом."""

    def __init__(
        self,
        name: str,
        searcher: MediaSearcher,
        extractor: PlaylistExtractor,
        *,
        query: str = "{artist} {album}",
        min_title_score: float = 0.7,
        max_candidates: int = 3,
        min_coverage: float = 1.0,
    ) -> None:
        self.name = name
        self._searcher = searcher
        self._extractor = extractor
        self._query = query
        self._min_title = min_title_score
        self._max_candidates = max_candidates
        self._min_coverage = min_coverage

    async def find(self, album: Album) -> SourceMatch | None:
        query = self._query.format(artist=album.artist, album=album.title)
        pages = await self._searcher.search(query, 10)
        pages = [
            p for p in pages
            if title_similarity(album.title, p.title) >= self._min_title
            and not has_negative_words(p.title, album.title)
        ]
        pages.sort(key=lambda p: title_similarity(album.title, p.title), reverse=True)
        for page in pages[: self._max_candidates]:
            entries = await self._extractor.extract(page.url)
            aligned = align_playlist(album, entries, min_coverage=self._min_coverage)
            if aligned:
                return SourceMatch(SourceKind.TRACKS, self.name, aligned, 1.0)
        return None


class PerTrackFinder:
    """Ищет каждый трек отдельно; принимает результат, только если найдено достаточно треков."""

    def __init__(
        self,
        searcher: MediaSearcher,
        *,
        name: str | None = None,
        query: str = "{artist} {track}",
        tolerance: float = 8.0,
        min_title_score: float = 0.75,
        min_coverage: float = 1.0,
        concurrency: int = 4,
        results_per_track: int = 8,
    ) -> None:
        self.name = name or f"{searcher.name}_tracks"
        self._searcher = searcher
        self._query = query
        self._tolerance = tolerance
        self._min_title = min_title_score
        self._min_coverage = min_coverage
        self._sem = asyncio.Semaphore(concurrency)
        self._per_track = results_per_track

    async def find(self, album: Album) -> SourceMatch | None:
        if not album.tracks:
            return None
        found = await asyncio.gather(*(self._find_track(album, t) for t in album.tracks))
        refs = tuple(r for r in found if r)
        if len(refs) < len(album.tracks) * self._min_coverage:
            log.info("%s: found %d/%d tracks", self.name, len(refs), len(album.tracks))
            return None
        return SourceMatch(SourceKind.TRACKS, self.name, refs, len(refs) / len(album.tracks))

    async def _find_track(self, album: Album, track: Track) -> MediaRef | None:
        artist = track.artist or album.artist
        async with self._sem:
            results = await self._searcher.search(
                self._query.format(artist=artist, track=track.title, album=album.title),
                self._per_track,
            )
        best: tuple[float, MediaRef] | None = None
        for ref in results:
            if has_negative_words(ref.title, f"{track.title} {album.title}"):
                continue
            t_score = title_similarity(track.title, ref.title)
            if t_score < self._min_title:
                continue
            if track.duration is not None:
                if not duration_matches(ref.duration, track.duration, absolute=self._tolerance):
                    continue
                d_score = duration_score(ref.duration, track.duration, self._tolerance)
            else:
                d_score = 0.5
            a_score = title_similarity(artist, f"{ref.uploader or ''} {ref.title}")
            score = 0.5 * t_score + 0.3 * d_score + 0.2 * a_score
            if best is None or score > best[0]:
                best = (score, ref)
        return _with_track(best[1], track) if best else None


class ChainSourceFinder:
    """Перебирает стратегии по порядку, возвращает первую удачную."""

    name = "chain"

    def __init__(self, finders: Sequence[SourceFinder]) -> None:
        self._finders = list(finders)

    async def find(self, album: Album) -> SourceMatch | None:
        for finder in self._finders:
            try:
                match = await finder.find(album)
            except Exception:  # одна сломанная площадка не должна ронять поиск
                log.exception("source finder %s failed", finder.name)
                continue
            if match:
                log.info("source found by %s", finder.name)
                return match
        return None


def align_playlist(
    album: Album,
    entries: Sequence[MediaRef],
    *,
    min_coverage: float = 1.0,
    duration_tol: float = 5.0,
) -> tuple[MediaRef, ...] | None:
    """Сопоставляет треки плейлиста с треклистом, сохраняя порядок.

    Плейлист может содержать бонус-треки — они пропускаются.
    """
    if not album.tracks or not entries:
        return None
    result: list[MediaRef] = []
    cursor = 0
    for track in album.tracks:
        for j in range(cursor, len(entries)):
            entry = entries[j]
            t_score = title_similarity(track.title, entry.title)
            dur_ok = duration_matches(entry.duration, track.duration, absolute=duration_tol)
            if t_score >= 0.8 or (dur_ok and t_score >= 0.5):
                result.append(_with_track(entry, track))
                cursor = j + 1
                break
    if len(result) < len(album.tracks) * min_coverage:
        return None
    return tuple(result)


def _with_track(ref: MediaRef, track: Track) -> MediaRef:
    return MediaRef(url=ref.url, title=ref.title, duration=ref.duration, uploader=ref.uploader, track=track)
