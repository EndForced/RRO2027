"""Сквозной тест пайплайна с фейковым скачиванием и настоящими ffmpeg + mutagen."""
import shutil
import subprocess

import pytest
from mutagen.id3 import ID3

from albumizer.ai import HeuristicQueryParser
from albumizer.media import FfmpegSplitter, MutagenTagger
from albumizer.media.processing import plan_segments
from albumizer.models import (
    Album,
    AlbumCandidate,
    Chapter,
    DownloadedMedia,
    MediaRef,
    SourceKind,
    SourceMatch,
    Track,
)
from albumizer.pipeline import AlbumPipeline

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")

ALBUM = Album(
    "Band", "Album", (Track(1, "One", 2.0), Track(2, "Two/Slash", 3.0)), year="2001", cover_url="http://c"
)


def make_mp3(path, seconds):
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
         "-i", f"sine=frequency=440:duration={seconds}", "-c:a", "libmp3lame", "-b:a", "64k", str(path)],
        check=True,
    )


def mp3_duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout)


class FakeDownloader:
    def __init__(self, lengths):
        self._lengths = lengths
        self.calls = []

    async def download(self, ref, dest_dir):
        self.calls.append(ref.url)
        path = dest_dir / f"{ref.url}.mp3"
        make_mp3(path, self._lengths[ref.url])
        return DownloadedMedia(path=path, duration=self._lengths[ref.url])


class FakeMetadata:
    name = "fake"

    async def search(self, query, limit=5):
        return [AlbumCandidate("fake", "1", query.artist or "?", query.album or "?")]

    async def get_album(self, candidate):
        return ALBUM


class FakeFinder:
    name = "fake"

    def __init__(self, match):
        self._match = match

    async def find(self, album):
        return self._match


class FakeCover:
    async def load(self, url):
        return b"\xff\xd8\xff\xe0fakejpeg"


def make_pipeline(tmp_path, downloader, match=None):
    return AlbumPipeline(
        parser=HeuristicQueryParser(),
        metadata=FakeMetadata(),
        finder=FakeFinder(match),
        downloader=downloader,
        splitter=FfmpegSplitter(),
        tagger=MutagenTagger(),
        cover_loader=FakeCover(),
        workdir=tmp_path,
    )


def test_plan_segments():
    tracks = (Track(1, "a", 10), Track(2, "b", 20), Track(3, "c", 30))
    assert plan_segments(tracks, 120, ()) == [(0, 20), (20, 40), (60, None)]
    chapters = (Chapter("a", 0, 11), Chapter("b", 11, 30), Chapter("c", 30, 61))
    assert plan_segments(tracks, 61, chapters) == [(0, 11), (11, 19), (30, 31)]
    with pytest.raises(ValueError):
        plan_segments((Track(1, "a"),), 10, ())


@needs_ffmpeg
async def test_full_album_is_split_and_tagged(tmp_path):
    match = SourceMatch(SourceKind.FULL_ALBUM, "youtube_full", (MediaRef("full", "Band - Album", 5),))
    pipeline = make_pipeline(tmp_path, FakeDownloader({"full": 5}), match)
    [cand] = await pipeline.search("Band - Album")
    album = await pipeline.load_album(cand)
    messages = []

    async def progress(msg):
        messages.append(msg)

    result = await pipeline.build(album, await pipeline.find_source(album), progress)
    assert [f.path.name for f in result.files] == ["01 - One.mp3", "02 - Two_Slash.mp3"]
    assert mp3_duration(result.files[0].path) == pytest.approx(2.0, abs=0.15)
    assert mp3_duration(result.files[1].path) == pytest.approx(3.0, abs=0.15)
    tags = ID3(result.files[1].path)
    assert str(tags["TIT2"]) == "Two/Slash" and str(tags["TRCK"]) == "2/2"
    assert tags.getall("APIC")
    assert messages

    pipeline.cleanup(result)
    assert not result.workdir.exists()


@needs_ffmpeg
async def test_per_track_source(tmp_path):
    match = SourceMatch(SourceKind.TRACKS, "youtube_tracks", (
        MediaRef("t2", "Two", 3, track=ALBUM.tracks[1]),
        MediaRef("t1", "One", 2, track=ALBUM.tracks[0]),
    ))
    downloader = FakeDownloader({"t1": 2, "t2": 3})
    result = await make_pipeline(tmp_path, downloader).build(ALBUM, match)
    assert sorted(downloader.calls) == ["t1", "t2"]
    assert [f.track.position for f in result.files] == [1, 2]
    assert str(ID3(result.files[0].path)["TALB"]) == "Album"


async def test_build_failure_cleans_up(tmp_path):
    class Boom:
        async def download(self, ref, dest_dir):
            raise RuntimeError("network")

    match = SourceMatch(SourceKind.FULL_ALBUM, "x", (MediaRef("u", "t", 5),))
    with pytest.raises(RuntimeError):
        await make_pipeline(tmp_path, Boom()).build(ALBUM, match)
    assert list(tmp_path.iterdir()) == []
