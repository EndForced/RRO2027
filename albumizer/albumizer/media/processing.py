"""Нарезка ffmpeg, ID3-теги, загрузка обложек."""
from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path

import httpx
from mutagen.id3 import APIC, ID3, TALB, TDRC, TIT2, TPE1, TPE2, TRCK

from ..models import Album, AudioFile, Chapter, DownloadedMedia, Track

log = logging.getLogger(__name__)

_UNSAFE = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def track_filename(track: Track, ext: str = "mp3") -> str:
    name = _UNSAFE.sub("_", track.title).strip(" .") or "track"
    return f"{track.position:02d} - {name[:100]}.{ext}"


def plan_segments(
    tracks: tuple[Track, ...], media_duration: float | None, chapters: tuple[Chapter, ...]
) -> list[tuple[float, float | None]]:
    """Границы треков внутри одного файла: (start, length|None до конца)."""
    if chapters and len(chapters) == len(tracks):
        return [(c.start, c.end - c.start) for c in chapters]

    if any(t.duration is None for t in tracks):
        raise ValueError("cannot split: tracklist has no durations and video has no chapters")
    expected = sum(t.duration for t in tracks)  # type: ignore[misc]
    # Видео часто длиннее/короче на паузы и интро — равномерно растягиваем.
    scale = media_duration / expected if media_duration and expected else 1.0
    segments: list[tuple[float, float | None]] = []
    pos = 0.0
    for i, t in enumerate(tracks):
        length = t.duration * scale  # type: ignore[operator]
        segments.append((pos, None if i == len(tracks) - 1 else length))
        pos += length
    return segments


class FfmpegSplitter:
    def __init__(self, ffmpeg: str = "ffmpeg") -> None:
        self._ffmpeg = ffmpeg

    async def split(self, media: DownloadedMedia, album: Album, dest_dir: Path) -> list[AudioFile]:
        dest_dir.mkdir(parents=True, exist_ok=True)
        segments = plan_segments(album.tracks, media.duration, media.chapters)
        ext = media.path.suffix.lstrip(".") or "mp3"
        files: list[AudioFile] = []
        for track, (start, length) in zip(album.tracks, segments, strict=True):
            out = dest_dir / track_filename(track, ext)
            cmd = [self._ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                   "-ss", f"{start:.3f}", "-i", str(media.path)]
            if length is not None:
                cmd += ["-t", f"{length:.3f}"]
            cmd += ["-map", "0:a", "-c", "copy", str(out)]
            await _run(cmd)
            files.append(AudioFile(path=out, track=track))
        return files


class MutagenTagger:
    async def tag(self, files: list[AudioFile], album: Album, cover: bytes | None) -> None:
        await asyncio.to_thread(self._tag_sync, files, album, cover)

    @staticmethod
    def _tag_sync(files: list[AudioFile], album: Album, cover: bytes | None) -> None:
        total = len(album.tracks)
        for f in files:
            tags = ID3()  # save() заменяет существующий ID3v2-тег целиком
            tags.add(TIT2(encoding=3, text=f.track.title))
            tags.add(TPE1(encoding=3, text=f.track.artist or album.artist))
            tags.add(TPE2(encoding=3, text=album.artist))
            tags.add(TALB(encoding=3, text=album.title))
            tags.add(TRCK(encoding=3, text=f"{f.track.position}/{total}"))
            if album.year:
                tags.add(TDRC(encoding=3, text=album.year))
            if cover:
                tags.add(APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=cover))
            tags.save(f.path)


class HttpCoverLoader:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def load(self, url: str) -> bytes | None:
        try:
            resp = await self._client.get(url, follow_redirects=True)
            resp.raise_for_status()
            return resp.content
        except httpx.HTTPError as exc:
            log.warning("cover download failed: %s", exc)
            return None


async def _run(cmd: list[str]) -> None:
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE
    )
    _, err = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"{cmd[0]} failed: {err.decode(errors='replace').strip()}")
