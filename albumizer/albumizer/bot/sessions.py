"""Состояние диалога. Хранилище за интерфейсом — легко заменить на Redis."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from ..models import Album, AlbumCandidate


@dataclass
class Session:
    version: int = 0  # растёт при каждом новом поиске, старые кнопки игнорируются
    candidates: list[AlbumCandidate] = field(default_factory=list)
    album: Album | None = None
    busy: bool = False

    def reset(self) -> None:
        self.version += 1
        self.candidates = []
        self.album = None


class SessionStore(Protocol):
    def get(self, key: str) -> Session: ...


class InMemorySessionStore:
    def __init__(self) -> None:
        self._data: dict[str, Session] = {}

    def get(self, key: str) -> Session:
        return self._data.setdefault(key, Session())
