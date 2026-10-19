"""Composition root: единственное место, где выбираются конкретные реализации."""
from __future__ import annotations

from typing import Any

import httpx

from .ai import FailoverLLM, HeuristicQueryParser, LLMQueryParser, LLMSourceJudge, OpenAICompatibleLLM
from .bot import AlbumBot
from .config import Settings
from .interfaces import LLMClient, QueryParser, SourceFinder, SourceJudge
from .media import (
    FfmpegSplitter,
    HttpCoverLoader,
    MutagenTagger,
    YtDlpDownloader,
    YtDlpPlaylistExtractor,
    YtDlpSearcher,
)
from .metadata import CompositeMetadata, DeezerMetadata, MusicBrainzMetadata
from .pipeline import AlbumPipeline
from .sources import (
    ArchiveOrgExtractor,
    ArchiveOrgSearcher,
    BandcampSearcher,
    ChainSourceFinder,
    FullAlbumVideoFinder,
    PerTrackFinder,
    PlaylistAlbumFinder,
)


def _ytdlp_opts(settings: Settings) -> dict[str, Any]:
    opts: dict[str, Any] = {}
    if settings.ytdlp_cookies:
        opts["cookiefile"] = settings.ytdlp_cookies
    if settings.ytdlp_proxy:
        opts["proxy"] = settings.ytdlp_proxy
    return opts


def build_llm(settings: Settings, client: httpx.AsyncClient) -> LLMClient | None:
    clients = [
        OpenAICompatibleLLM(p.base_url, p.api_key, p.model, client=client)
        for p in settings.llm_providers
    ]
    return FailoverLLM(clients) if clients else None


def build_source_finder(
    settings: Settings, client: httpx.AsyncClient, judge: SourceJudge | None
) -> SourceFinder:
    ytdlp_opts = _ytdlp_opts(settings)
    youtube = YtDlpSearcher("youtube", "ytsearch{limit}:{query}", extra_opts=ytdlp_opts)
    factories = {
        "youtube_full": lambda: FullAlbumVideoFinder(youtube, judge=judge),
        "ytmusic_album": lambda: PlaylistAlbumFinder(
            "ytmusic_album",
            YtDlpSearcher(
                "ytmusic", "https://music.youtube.com/search?q={query}#albums", extra_opts=ytdlp_opts
            ),
            YtDlpPlaylistExtractor(extra_opts=ytdlp_opts),
        ),
        "bandcamp": lambda: PlaylistAlbumFinder(
            "bandcamp",
            BandcampSearcher(client),
            # flat-режим Bandcamp не отдаёт длительности, поэтому полная экстракция
            YtDlpPlaylistExtractor(flat=False, extra_opts=ytdlp_opts),
        ),
        "archive_org": lambda: PlaylistAlbumFinder(
            "archive_org", ArchiveOrgSearcher(client), ArchiveOrgExtractor(client)
        ),
        "youtube_tracks": lambda: PerTrackFinder(youtube, query="{artist} {track} audio"),
        "soundcloud_tracks": lambda: PerTrackFinder(
            # в flat-выдаче SoundCloud нет длительностей
            YtDlpSearcher("soundcloud", "scsearch{limit}:{query}", flat=False, extra_opts=ytdlp_opts),
            results_per_track=5,
        ),
    }
    unknown = set(settings.sources) - factories.keys()
    if unknown:
        raise ValueError(f"unknown sources: {', '.join(sorted(unknown))}; known: {', '.join(factories)}")
    return ChainSourceFinder([factories[name]() for name in settings.sources])


def build_pipeline(settings: Settings, client: httpx.AsyncClient) -> AlbumPipeline:
    llm = build_llm(settings, client)
    parser: QueryParser = LLMQueryParser(llm) if llm else HeuristicQueryParser()
    judge = LLMSourceJudge(llm) if llm and settings.llm_judge else None

    ytdlp_opts = _ytdlp_opts(settings)

    settings.workdir.mkdir(parents=True, exist_ok=True)
    return AlbumPipeline(
        parser=parser,
        metadata=CompositeMetadata(
            [DeezerMetadata(client), MusicBrainzMetadata(client, settings.musicbrainz_user_agent)]
        ),
        finder=build_source_finder(settings, client, judge),
        downloader=YtDlpDownloader(audio_quality=settings.audio_quality, extra_opts=ytdlp_opts),
        splitter=FfmpegSplitter(),
        tagger=MutagenTagger(),
        cover_loader=HttpCoverLoader(client),
        workdir=settings.workdir.resolve(),
        download_concurrency=settings.download_concurrency,
    )


async def main() -> None:
    settings = Settings.from_env()
    async with httpx.AsyncClient(timeout=30.0) as client:
        bot = AlbumBot(
            build_pipeline(settings, client),
            allowed_users=set(settings.allowed_users) if settings.allowed_users else None,
            max_parallel_jobs=settings.max_parallel_jobs,
        )
        await bot.run(settings.bot_token)
