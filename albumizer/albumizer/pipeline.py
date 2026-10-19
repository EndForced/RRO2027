"""Оркестратор: запрос → метаданные → источник → скачивание → нарезка → теги."""
from __future__ import annotations

import asyncio
import logging
import shutil
import uuid
from pathlib import Path

from .interfaces import (
    AudioSplitter,
    CoverLoader,
    Downloader,
    MetadataProvider,
    ProgressReporter,
    QueryParser,
    SourceFinder,
    Tagger,
)
from .media.processing import track_filename
from .models import Album, AlbumCandidate, AlbumResult, AudioFile, SourceKind, SourceMatch

log = logging.getLogger(__name__)


async def _silent(_: str) -> None:
    return None


class AlbumPipeline:
    def __init__(
        self,
        *,
        parser: QueryParser,
        metadata: MetadataProvider,
        finder: SourceFinder,
        downloader: Downloader,
        splitter: AudioSplitter,
        tagger: Tagger,
        workdir: Path,
        cover_loader: CoverLoader | None = None,
        download_concurrency: int = 3,
    ) -> None:
        self._parser = parser
        self._metadata = metadata
        self._finder = finder
        self._downloader = downloader
        self._splitter = splitter
        self._tagger = tagger
        self._cover_loader = cover_loader
        self._workdir = workdir
        self._concurrency = download_concurrency

    async def search(self, text: str, limit: int = 6) -> list[AlbumCandidate]:
        query = await self._parser.parse(text)
        log.info("parsed %r → %s", text, query)
        return await self._metadata.search(query, limit)

    async def load_album(self, candidate: AlbumCandidate) -> Album:
        return await self._metadata.get_album(candidate)

    async def find_source(self, album: Album) -> SourceMatch | None:
        return await self._finder.find(album)

    async def build(
        self, album: Album, source: SourceMatch, progress: ProgressReporter | None = None
    ) -> AlbumResult:
        report = progress or _silent
        job_dir = self._workdir / uuid.uuid4().hex
        job_dir.mkdir(parents=True, exist_ok=True)
        result = AlbumResult(album=album, source=source, workdir=job_dir)
        cover_task = asyncio.create_task(self._load_cover(album))
        try:
            if source.kind is SourceKind.FULL_ALBUM:
                result.files = await self._build_from_full(album, source, job_dir, report)
            else:
                result.files = await self._build_from_tracks(source, job_dir, report)
            await report("🏷 Проставляю теги…")
            await self._tagger.tag(result.files, album, await cover_task)
        except BaseException:
            cover_task.cancel()
            shutil.rmtree(job_dir, ignore_errors=True)
            raise
        result.files.sort(key=lambda f: f.track.position)
        return result

    def cleanup(self, result: AlbumResult) -> None:
        if result.workdir and self._workdir in result.workdir.parents:
            shutil.rmtree(result.workdir, ignore_errors=True)

    async def _build_from_full(
        self, album: Album, source: SourceMatch, job_dir: Path, report: ProgressReporter
    ) -> list[AudioFile]:
        await report("⬇️ Скачиваю альбом одним файлом…")
        media = await self._downloader.download(source.items[0], job_dir / "raw")
        await report("✂️ Режу на треки…")
        files = await self._splitter.split(media, album, job_dir / "tracks")
        media.path.unlink(missing_ok=True)
        return files

    async def _build_from_tracks(
        self, source: SourceMatch, job_dir: Path, report: ProgressReporter
    ) -> list[AudioFile]:
        sem = asyncio.Semaphore(self._concurrency)
        total = len(source.items)
        done = 0
        out_dir = job_dir / "tracks"
        out_dir.mkdir(parents=True, exist_ok=True)

        async def fetch(index: int) -> AudioFile:
            nonlocal done
            ref = source.items[index]
            if ref.track is None:
                raise ValueError(f"media {ref.url} is not bound to a track")
            async with sem:
                media = await self._downloader.download(ref, job_dir / f"raw{index}")
            target = out_dir / track_filename(ref.track, media.path.suffix.lstrip(".") or "mp3")
            shutil.move(media.path, target)
            done += 1
            await report(f"⬇️ Скачано {done}/{total}")
            return AudioFile(path=target, track=ref.track)

        await report(f"⬇️ Скачиваю {total} треков…")
        return list(await asyncio.gather(*(fetch(i) for i in range(total))))

    async def _load_cover(self, album: Album) -> bytes | None:
        if not (self._cover_loader and album.cover_url):
            return None
        return await self._cover_loader.load(album.cover_url)
