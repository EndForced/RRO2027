"""Парсинг ответов внешних API на фикстурах (через httpx.MockTransport)."""
import httpx

from albumizer.metadata import CompositeMetadata, DeezerMetadata, MusicBrainzMetadata
from albumizer.models import AlbumQuery
from albumizer.sources.archive_org import ArchiveOrgExtractor, ArchiveOrgSearcher
from albumizer.sources.bandcamp import parse_search_page


def _client(routes):
    def handler(request: httpx.Request) -> httpx.Response:
        for prefix, payload in routes.items():
            if request.url.path.startswith(prefix):
                if isinstance(payload, Exception):
                    raise payload
                return httpx.Response(200, json=payload)
        return httpx.Response(404, json={})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


DEEZER = {
    "/search/album": {"data": [{"id": 12047952, "title": "OK Computer", "nb_tracks": 12,
                                "artist": {"name": "Radiohead"}}]},
    "/album/12047952": {
        "title": "OK Computer", "release_date": "1997-05-21", "cover_xl": "https://img/x.jpg",
        "artist": {"name": "Radiohead"},
        "tracks": {"data": [
            {"title": "Airbag", "duration": 284, "artist": {"name": "Radiohead"}},
            {"title": "Paranoid Android", "duration": 383, "artist": {"name": "Radiohead"}},
        ]},
    },
}

MB = {
    "/ws/2/release/abc": {
        "title": "OK Computer", "date": "1997-05-21",
        "artist-credit": [{"name": "Radiohead", "joinphrase": ""}],
        "cover-art-archive": {"front": True},
        "media": [{"tracks": [
            {"title": "Airbag", "length": 284000, "artist-credit": [{"name": "Radiohead"}]},
            {"title": "Feat Song", "length": None, "recording": {"length": 100000},
             "artist-credit": [{"name": "Radiohead", "joinphrase": " feat. "}, {"name": "Guest"}]},
        ]}],
    },
    "/ws/2/release": {"releases": [
        {"id": "abc", "title": "OK Computer", "date": "1997", "track-count": 12,
         "artist-credit": [{"name": "Radiohead"}]},
        {"id": "dup", "title": "OK Computer", "date": "2009", "track-count": 12,
         "artist-credit": [{"name": "Radiohead"}]},
    ]},
}


async def test_deezer():
    async with _client(DEEZER) as client:
        provider = DeezerMetadata(client)
        [cand] = await provider.search(AlbumQuery("x", "Radiohead", "OK Computer"))
        album = await provider.get_album(cand)
    assert album.year == "1997" and album.total_duration == 667
    assert album.tracks[1].title == "Paranoid Android" and album.tracks[1].artist is None


async def test_musicbrainz_dedupes_and_parses_credits():
    async with _client(MB) as client:
        provider = MusicBrainzMetadata(client, "test/1.0", min_interval=0)
        cands = await provider.search(AlbumQuery("ok computer"))
        assert len(cands) == 1
        album = await provider.get_album(cands[0])
    assert [t.duration for t in album.tracks] == [284, 100]
    assert album.tracks[1].artist == "Radiohead feat. Guest"
    assert album.cover_url and "abc" in album.cover_url


async def test_composite_survives_failing_provider():
    async with _client({**DEEZER, "/ws/2": httpx.ConnectError("down")}) as client:
        composite = CompositeMetadata([DeezerMetadata(client), MusicBrainzMetadata(client, "t", 0)])
        cands = await composite.search(AlbumQuery("ok computer"))
        assert [c.provider for c in cands] == ["deezer"]
        album = await composite.get_album(cands[0])
    assert album.source == "deezer"


async def test_archive_org():
    routes = {
        "/advancedsearch.php": {"response": {"docs": [
            {"identifier": "item1", "title": "Some Album", "creator": ["Band"]}]}},
        "/metadata/item1": {"files": [
            {"name": "02 Second.mp3", "format": "VBR MP3", "title": "Second", "length": "3:05", "track": "2"},
            {"name": "01 First.mp3", "format": "VBR MP3", "length": "120.5", "track": "1/2"},
            {"name": "01 First.flac", "format": "Flac", "length": "120.5", "track": "1"},
        ]},
    }
    async with _client(routes) as client:
        [page] = await ArchiveOrgSearcher(client).search("Band Some Album")
        entries = await ArchiveOrgExtractor(client).extract(page.url)
    assert page.uploader == "Band"
    assert [(e.title, e.duration) for e in entries] == [("First", 120.5), ("Second", 185.0)]
    assert entries[0].url == "https://archive.org/download/item1/01%20First.mp3"


def test_bandcamp_search_page():
    html = """
    <ul><li class="searchresult data-search"><div class="result-info">
      <div class="itemtype">ALBUM</div>
      <div class="heading"><a href="https://band.bandcamp.com/album/x?from=search">Some Album</a></div>
      <div class="subhead">by Band</div>
      <div class="itemurl"><a href="https://band.bandcamp.com/album/x">https://band.bandcamp.com/album/x</a></div>
    </div></li>
    <li class="searchresult"><div class="itemtype">TRACK</div>
      <div class="heading"><a href="https://t">Track</a></div></li></ul>
    """
    [ref] = parse_search_page(html)
    assert (ref.url, ref.title, ref.uploader) == ("https://band.bandcamp.com/album/x", "Some Album", "Band")
