"""Тексты сообщений (HTML parse mode)."""
from __future__ import annotations

from html import escape

from ..matching import format_duration
from ..models import Album, SourceMatch

HELP = (
    "🎧 <b>Альбомизатор</b>\n\n"
    "Пришли название альбома, например:\n"
    "<code>Radiohead - OK Computer</code>\n"
    "или просто <code>пинк флойд дарк сайд</code>.\n\n"
    "Я найду треклист, ты подтвердишь, а я соберу альбом: сначала ищу полный "
    "альбом на YouTube, если не нашёл — на других площадках."
)

MAX_MESSAGE = 4000


def tracklist(album: Album) -> str:
    year = f" ({escape(album.year)})" if album.year else ""
    lines = [f"<b>{escape(album.artist)} — {escape(album.title)}</b>{year}", ""]
    for t in album.tracks:
        feat = f" <i>({escape(t.artist)})</i>" if t.artist else ""
        lines.append(f"{t.position}. {escape(t.title)}{feat} — {format_duration(t.duration)}")
    total = album.total_duration
    lines += [
        "",
        f"Треков: {len(album.tracks)}, общая длина: <b>{format_duration(total)}</b>",
        f"<i>метаданные: {escape(album.source or '?')}</i>",
    ]
    if total is None:
        lines.append("⚠️ Длина некоторых треков неизвестна — полный альбом одним видео искать не смогу.")
    lines += ["", "Это тот альбом?"]
    text = "\n".join(lines)
    return text if len(text) <= MAX_MESSAGE else text[: MAX_MESSAGE - 1] + "…"


def source_found(match: SourceMatch) -> str:
    return f"✅ Нашёл источник — {escape(match.description)}"


def done(album: Album, sent: int, skipped: list[str]) -> str:
    text = f"🎉 Готово: {escape(album.artist)} — {escape(album.title)}, отправлено треков: {sent}"
    if skipped:
        text += "\n⚠️ Не отправлены (слишком большие или отсутствуют): " + ", ".join(map(escape, skipped))
    return text
