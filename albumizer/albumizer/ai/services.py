"""Прикладные AI-сервисы. Каждый имеет не-AI запасной вариант."""
from __future__ import annotations

import logging
import re

from ..interfaces import LLMClient, QueryParser
from ..matching import format_duration
from ..models import Album, AlbumQuery, MediaRef
from .llm import LLMError, extract_json

log = logging.getLogger(__name__)

_SEPARATORS = re.compile(r"\s+[-–—:|]\s+|\s*[«\"](?=.)")


class HeuristicQueryParser:
    """«Artist - Album» / «Artist — Album» / «Artist "Album"». Иначе — свободный текст."""

    async def parse(self, text: str) -> AlbumQuery:
        text = " ".join(text.split())
        parts = [p.strip(" «»\"'") for p in _SEPARATORS.split(text, maxsplit=1)]
        if len(parts) == 2 and all(parts):
            return AlbumQuery(raw=text, artist=parts[0], album=parts[1])
        return AlbumQuery(raw=text)


class LLMQueryParser:
    """Разбирает «пинк флойд дарк сайд» → Pink Floyd / The Dark Side of the Moon."""

    SYSTEM = (
        "You extract a music album request. Reply ONLY with JSON: "
        '{"artist": string|null, "album": string|null}. '
        "Fix typos and transliteration, use the official (usually original-language) "
        "artist and album names. If unsure, keep the user's spelling."
    )

    def __init__(self, llm: LLMClient, fallback: QueryParser | None = None) -> None:
        self._llm = llm
        self._fallback = fallback or HeuristicQueryParser()

    async def parse(self, text: str) -> AlbumQuery:
        try:
            data = extract_json(await self._llm.complete(self.SYSTEM, text))
            artist = (data.get("artist") or "").strip() or None
            album = (data.get("album") or "").strip() or None
            if artist or album:
                return AlbumQuery(raw=text, artist=artist, album=album)
        except LLMError as exc:
            log.warning("LLM query parse failed, using heuristic: %s", exc)
        return await self._fallback.parse(text)


class LLMSourceJudge:
    """Отсекает каверы, live-версии, реакции и т.п., которые прошли по длительности."""

    SYSTEM = (
        "You verify whether a video is the complete original studio album. "
        'Reply ONLY with JSON: {"match": true|false, "reason": string}. '
        "Reject covers, live versions, reactions, reviews, remixes, slowed/8D edits, "
        "and compilations of a different album."
    )

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def is_full_album(self, album: Album, ref: MediaRef) -> bool:
        prompt = (
            f"Album: {album.artist} — {album.title} ({album.year or 'year unknown'}), "
            f"{len(album.tracks)} tracks, total {format_duration(album.total_duration)}.\n"
            f"Video title: {ref.title}\nChannel: {ref.uploader or 'unknown'}\n"
            f"Video length: {format_duration(ref.duration)}"
        )
        try:
            return bool(extract_json(await self._llm.complete(self.SYSTEM, prompt)).get("match"))
        except LLMError as exc:
            log.warning("LLM judge failed, accepting candidate: %s", exc)
            return True  # длительность уже совпала — не блокируем из-за сбоя AI
