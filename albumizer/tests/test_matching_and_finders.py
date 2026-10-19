import pytest

from albumizer.ai import HeuristicQueryParser, LLMQueryParser
from albumizer.ai.llm import FailoverLLM, LLMError, extract_json
from albumizer.matching import duration_matches, format_duration, has_negative_words, title_similarity
from albumizer.models import Album, MediaRef, SourceKind, Track
from albumizer.sources import (
    ChainSourceFinder,
    FullAlbumVideoFinder,
    PerTrackFinder,
    PlaylistAlbumFinder,
    align_playlist,
)

ALBUM = Album(
    artist="Radiohead",
    title="OK Computer",
    year="1997",
    tracks=(
        Track(1, "Airbag", 284),
        Track(2, "Paranoid Android", 383),
        Track(3, "Subterranean Homesick Alien", 267),
    ),
)
TOTAL = 284 + 383 + 267


class FakeSearcher:
    def __init__(self, name="fake", results=None, by_query=None):
        self.name = name
        self._results = results or []
        self._by_query = by_query or {}
        self.queries = []

    async def search(self, query, limit=10):
        self.queries.append(query)
        for key, refs in self._by_query.items():
            if key.lower() in query.lower():
                return refs
        return self._results


class FakeExtractor:
    def __init__(self, pages):
        self._pages = pages

    async def extract(self, url):
        return self._pages.get(url, [])


class RejectAll:
    async def is_full_album(self, album, ref):
        return False


def test_matching_helpers():
    assert title_similarity("OK Computer", "Radiohead - OK Computer (Full Album) [HQ]") > 0.9
    assert title_similarity("OK Computer", "Kid A") < 0.6
    assert has_negative_words("OK Computer piano cover", "OK Computer")
    assert not has_negative_words("Live Through This full album", "Live Through This")
    assert duration_matches(100, 105, absolute=10)
    assert not duration_matches(None, 105)
    assert format_duration(3725) == "1:02:05"
    assert format_duration(65) == "1:05"


async def test_full_album_finder_picks_duration_match_and_skips_covers():
    searcher = FakeSearcher(results=[
        MediaRef("u1", "Radiohead - OK Computer (Full Album)", TOTAL + 600, "fan"),  # не та длина
        MediaRef("u2", "OK Computer full album piano cover", TOTAL, "pianist"),  # кавер
        MediaRef("u3", "Radiohead - OK Computer [Full Album]", TOTAL + 12, "Radiohead"),
    ])
    match = await FullAlbumVideoFinder(searcher).find(ALBUM)
    assert match and match.kind is SourceKind.FULL_ALBUM
    assert match.items[0].url == "u3"


async def test_full_album_finder_respects_judge():
    searcher = FakeSearcher(results=[MediaRef("u3", "Radiohead - OK Computer", TOTAL, "Radiohead")])
    assert await FullAlbumVideoFinder(searcher, judge=RejectAll()).find(ALBUM) is None


async def test_per_track_finder_requires_all_tracks():
    by_query = {
        "airbag": [MediaRef("a", "Radiohead - Airbag", 285, "Radiohead - Topic")],
        "paranoid": [
            MediaRef("p0", "Paranoid Android (live)", 383, "x"),
            MediaRef("p", "Paranoid Android", 380, "Radiohead - Topic"),
        ],
        "subterranean": [MediaRef("s", "Subterranean Homesick Alien", 267, "Radiohead")],
    }
    match = await PerTrackFinder(FakeSearcher(by_query=by_query)).find(ALBUM)
    assert match and [r.url for r in match.items] == ["a", "p", "s"]
    assert [r.track.position for r in match.items] == [1, 2, 3]

    del by_query["subterranean"]
    assert await PerTrackFinder(FakeSearcher(by_query=by_query)).find(ALBUM) is None


def test_align_playlist_skips_bonus_tracks():
    entries = [
        MediaRef("1", "Airbag", 284),
        MediaRef("bonus", "Airbag (demo)", 200),
        MediaRef("2", "Paranoid Android", 384),
        MediaRef("3", "Subterranean Homesick Alien (Remastered)", 268),
    ]
    aligned = align_playlist(ALBUM, entries)
    assert aligned and [r.url for r in aligned] == ["1", "2", "3"]
    assert align_playlist(ALBUM, entries[:2]) is None


async def test_playlist_finder_and_chain_order():
    pages = FakeSearcher(results=[MediaRef("page", "OK Computer", None, "Radiohead")])
    extractor = FakeExtractor({"page": [
        MediaRef("1", "Airbag", 284), MediaRef("2", "Paranoid Android", 383),
        MediaRef("3", "Subterranean Homesick Alien", 267),
    ]})
    empty = FullAlbumVideoFinder(FakeSearcher(results=[]))

    class Broken:
        name = "broken"

        async def find(self, album):
            raise RuntimeError("site is down")

    chain = ChainSourceFinder([empty, Broken(), PlaylistAlbumFinder("bandcamp", pages, extractor)])
    match = await chain.find(ALBUM)
    assert match and match.provider == "bandcamp" and len(match.items) == 3


async def test_query_parsers():
    q = await HeuristicQueryParser().parse("Radiohead — OK Computer")
    assert (q.artist, q.album) == ("Radiohead", "OK Computer")
    q = await HeuristicQueryParser().parse("radiohead ok computer")
    assert q.artist is None and q.text == "radiohead ok computer"

    class GoodLLM:
        async def complete(self, system, user):
            return '```json\n{"artist": "Pink Floyd", "album": "The Dark Side of the Moon"}\n```'

    class BadLLM:
        async def complete(self, system, user):
            raise LLMError("rate limited")

    q = await LLMQueryParser(FailoverLLM([BadLLM(), GoodLLM()])).parse("пинк флойд дарк сайд")
    assert (q.artist, q.album) == ("Pink Floyd", "The Dark Side of the Moon")
    q = await LLMQueryParser(BadLLM()).parse("Pink Floyd - Animals")
    assert (q.artist, q.album) == ("Pink Floyd", "Animals")


def test_extract_json_errors():
    with pytest.raises(LLMError):
        extract_json("no json here")
