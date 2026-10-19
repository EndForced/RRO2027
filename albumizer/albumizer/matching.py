"""Чистые функции сравнения: длительности, названия, стоп-слова."""
from __future__ import annotations

import re

from rapidfuzz import fuzz

# Слова, которые почти всегда означают «не то» (если их нет в названии альбома).
NEGATIVE_WORDS = (
    "cover", "reaction", "karaoke", "instrumental", "remix", "8d", "slowed",
    "reverb", "nightcore", "sped up", "tutorial", "lesson", "review", "live",
    "кавер", "реакция", "разбор", "минус",
)

_BRACKETS = re.compile(r"[\(\[].*?[\)\]]")
_NON_WORD = re.compile(r"[^\w\s]", re.UNICODE)


def normalize(text: str) -> str:
    text = _BRACKETS.sub(" ", text.lower())
    text = _NON_WORD.sub(" ", text)
    return " ".join(text.split())


def title_similarity(expected: str, actual: str) -> float:
    """0..1 — насколько `actual` содержит/похож на `expected`."""
    a, b = normalize(expected), normalize(actual)
    if not a or not b:
        return 0.0
    return max(fuzz.token_set_ratio(a, b), fuzz.partial_ratio(a, b)) / 100.0


def has_negative_words(candidate: str, reference: str) -> bool:
    cand, ref = candidate.lower(), reference.lower()
    return any(
        re.search(rf"\b{re.escape(w)}\b", cand) and w not in ref for w in NEGATIVE_WORDS
    )


def duration_tolerance(expected: float, *, absolute: float, relative: float) -> float:
    return max(absolute, expected * relative)


def duration_matches(
    actual: float | None,
    expected: float | None,
    *,
    absolute: float = 10.0,
    relative: float = 0.0,
) -> bool:
    if actual is None or expected is None:
        return False
    return abs(actual - expected) <= duration_tolerance(expected, absolute=absolute, relative=relative)


def duration_score(actual: float | None, expected: float | None, tolerance: float) -> float:
    """1.0 при точном совпадении, линейно падает до 0 на границе допуска."""
    if actual is None or expected is None or tolerance <= 0:
        return 0.0
    return max(0.0, 1.0 - abs(actual - expected) / tolerance)


def format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "?:??"
    seconds = int(round(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
