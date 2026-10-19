"""Объединяет несколько провайдеров метаданных в один."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence

from ..interfaces import MetadataProvider
from ..models import Album, AlbumCandidate, AlbumQuery

log = logging.getLogger(__name__)


class CompositeMetadata:
    name = "composite"

    def __init__(self, providers: Sequence[MetadataProvider]) -> None:
        self._providers = {p.name: p for p in providers}

    async def search(self, query: AlbumQuery, limit: int = 5) -> list[AlbumCandidate]:
        results = await asyncio.gather(
            *(p.search(query, limit) for p in self._providers.values()), return_exceptions=True
        )
        merged: list[AlbumCandidate] = []
        seen: set[tuple[str, str]] = set()
        # Чередуем провайдеров, чтобы лучшие результаты каждого были наверху.
        lists = []
        for provider, res in zip(self._providers, results, strict=True):
            if isinstance(res, BaseException):
                log.warning("metadata provider %s failed: %s", provider, res)
                continue
            lists.append(res)
        for row in range(max((len(x) for x in lists), default=0)):
            for lst in lists:
                if row < len(lst):
                    cand = lst[row]
                    key = (cand.artist.casefold(), cand.title.casefold())
                    if key not in seen:
                        seen.add(key)
                        merged.append(cand)
        return merged[:limit]

    async def get_album(self, candidate: AlbumCandidate) -> Album:
        provider = self._providers.get(candidate.provider)
        if provider is None:
            raise LookupError(f"unknown metadata provider {candidate.provider!r}")
        return await provider.get_album(candidate)
