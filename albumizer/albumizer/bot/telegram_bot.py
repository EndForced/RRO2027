"""Telegram-слой. Знает только про AlbumService и SessionStore."""
from __future__ import annotations

import asyncio
import logging
import time
from html import escape

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.filters.callback_data import CallbackData
from aiogram.types import CallbackQuery, FSInputFile, InputMediaAudio, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from ..interfaces import AlbumService
from ..models import AlbumCandidate, AlbumResult
from . import texts
from .sessions import InMemorySessionStore, Session, SessionStore

log = logging.getLogger(__name__)

TELEGRAM_UPLOAD_LIMIT = 50 * 1024 * 1024
MEDIA_GROUP_SIZE = 10


class PickAlbum(CallbackData, prefix="pick"):
    v: int
    index: int


class Action(CallbackData, prefix="act"):
    v: int
    name: str  # confirm | back | cancel


class MessageProgress:
    """Редактирует статус-сообщение не чаще раза в `interval` секунд."""

    def __init__(self, message: Message, interval: float = 2.0) -> None:
        self._message = message
        self._interval = interval
        self._last = 0.0

    async def __call__(self, text: str) -> None:
        now = time.monotonic()
        if now - self._last < self._interval:
            return
        self._last = now
        await _safe_edit(self._message, text)


class AlbumBot:
    def __init__(
        self,
        service: AlbumService,
        *,
        sessions: SessionStore | None = None,
        allowed_users: set[int] | None = None,
        max_parallel_jobs: int = 2,
        upload_limit: int = TELEGRAM_UPLOAD_LIMIT,
    ) -> None:
        self._service = service
        self._sessions = sessions or InMemorySessionStore()
        self._allowed = allowed_users
        self._jobs = asyncio.Semaphore(max_parallel_jobs)
        self._upload_limit = upload_limit
        self.router = Router(name="albumizer")
        self._register()

    async def run(self, token: str) -> None:
        bot = Bot(token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        dp = Dispatcher()
        dp.include_router(self.router)
        await dp.start_polling(bot)

    # ---- регистрация -------------------------------------------------------

    def _register(self) -> None:
        r = self.router
        if self._allowed is not None:
            allowed = F.from_user.id.in_(self._allowed)
            r.message.filter(allowed)
            r.callback_query.filter(allowed)
        r.message.register(self.on_help, CommandStart())
        r.message.register(self.on_help, Command("help"))
        r.message.register(self.on_query, F.text & ~F.text.startswith("/"))
        r.callback_query.register(self.on_pick, PickAlbum.filter())
        r.callback_query.register(self.on_action, Action.filter())

    # ---- обработчики -------------------------------------------------------

    async def on_help(self, message: Message) -> None:
        await message.answer(texts.HELP)

    async def on_query(self, message: Message) -> None:
        session = self._session(message.chat.id, message.from_user.id if message.from_user else 0)
        if session.busy:
            await message.answer("⏳ Ещё собираю предыдущий альбом, подожди немного.")
            return
        session.reset()
        status = await message.answer("🔎 Ищу альбом…")
        try:
            candidates = await self._service.search(message.text or "")
        except Exception:
            log.exception("search failed")
            await _safe_edit(status, "❌ Поиск метаданных не удался, попробуй ещё раз.")
            return
        if not candidates:
            await _safe_edit(status, "🤷 Ничего не нашёл. Попробуй формат <code>Исполнитель - Альбом</code>.")
            return
        session.candidates = candidates
        await _safe_edit(status, "Выбери альбом:", self._candidates_kb(session.version, candidates))

    async def on_pick(self, query: CallbackQuery, callback_data: PickAlbum) -> None:
        session = self._session_for(query)
        message = query.message
        if not self._fresh(session, callback_data.v) or not isinstance(message, Message):
            await query.answer("Это старый запрос, пришли название заново.", show_alert=True)
            return
        if not 0 <= callback_data.index < len(session.candidates):
            await query.answer("Нет такого варианта")
            return
        await query.answer()
        await _safe_edit(message, "📀 Загружаю треклист…")
        try:
            album = await self._service.load_album(session.candidates[callback_data.index])
        except Exception:
            log.exception("load album failed")
            await _safe_edit(message, "❌ Не удалось получить треклист.", self._back_kb(session.version))
            return
        if not album.tracks:
            await _safe_edit(message, "🤷 У этого релиза пустой треклист.", self._back_kb(session.version))
            return
        session.album = album
        await _safe_edit(message, texts.tracklist(album), self._confirm_kb(session.version))

    async def on_action(self, query: CallbackQuery, callback_data: Action) -> None:
        session = self._session_for(query)
        message = query.message
        if not self._fresh(session, callback_data.v) or not isinstance(message, Message):
            await query.answer("Это старый запрос, пришли название заново.", show_alert=True)
            return
        await query.answer()
        if callback_data.name == "cancel":
            session.reset()
            await _safe_edit(message, "Отменено. Пришли другое название.")
        elif callback_data.name == "back":
            session.album = None
            await _safe_edit(message, "Выбери альбом:", self._candidates_kb(session.version, session.candidates))
        elif callback_data.name == "confirm" and session.album and not session.busy:
            session.busy = True
            try:
                await self._process(message, session)
            finally:
                session.busy = False
                session.reset()

    # ---- сборка и отправка -------------------------------------------------

    async def _process(self, message: Message, session: Session) -> None:
        album = session.album
        assert album is not None
        await _safe_edit(message, f"🔎 Ищу источник для <b>{escape(album.title)}</b>…")
        if self._jobs.locked():
            await _safe_edit(message, "⏳ В очереди — сейчас собираются другие альбомы…")
        async with self._jobs:
            try:
                match = await self._service.find_source(album)
            except Exception:
                log.exception("source search failed")
                await _safe_edit(message, "❌ Ошибка при поиске источника.")
                return
            if match is None:
                await _safe_edit(message, "😔 Не нашёл этот альбом ни на одной площадке.")
                return
            await _safe_edit(message, texts.source_found(match))
            progress = MessageProgress(message)
            try:
                result = await self._service.build(album, match, progress)
            except Exception as exc:
                log.exception("build failed")
                await _safe_edit(message, f"❌ Не удалось собрать альбом: {escape(str(exc))[:300]}")
                return
        try:
            await _safe_edit(message, "📤 Отправляю…")
            sent, skipped = await self._send(message, result)
            await _safe_edit(message, texts.done(album, sent, skipped))
        finally:
            self._service.cleanup(result)

    async def _send(self, message: Message, result: AlbumResult) -> tuple[int, list[str]]:
        album = result.album
        if album.cover_url:
            try:
                await message.answer_photo(
                    album.cover_url, caption=f"<b>{escape(album.artist)} — {escape(album.title)}</b>"
                )
            except TelegramBadRequest as exc:
                log.warning("cover send failed: %s", exc)

        present = {f.track.position for f in result.files}
        skipped = [t.title for t in album.tracks if t.position not in present]
        media: list[InputMediaAudio] = []
        for f in result.files:
            if f.path.stat().st_size > self._upload_limit:
                skipped.append(f.track.title)
                continue
            media.append(
                InputMediaAudio(
                    media=FSInputFile(f.path),
                    title=f.track.title,
                    performer=f.track.artist or album.artist,
                    duration=int(f.track.duration) if f.track.duration else None,
                )
            )
        for i in range(0, len(media), MEDIA_GROUP_SIZE):
            chunk = media[i : i + MEDIA_GROUP_SIZE]
            if len(chunk) == 1:
                one = chunk[0]
                await message.answer_audio(
                    one.media, title=one.title, performer=one.performer, duration=one.duration
                )
            else:
                await message.answer_media_group(chunk)
        return len(media), skipped

    # ---- вспомогательное ---------------------------------------------------

    def _session(self, chat_id: int, user_id: int) -> Session:
        return self._sessions.get(f"{chat_id}:{user_id}")

    def _session_for(self, query: CallbackQuery) -> Session:
        chat_id = query.message.chat.id if query.message else query.from_user.id
        return self._session(chat_id, query.from_user.id)

    @staticmethod
    def _fresh(session: Session, version: int) -> bool:
        return session.version == version

    @staticmethod
    def _candidates_kb(v: int, candidates: list[AlbumCandidate]):
        kb = InlineKeyboardBuilder()
        for i, c in enumerate(candidates):
            label = c.label if len(c.label) <= 60 else c.label[:59] + "…"
            kb.button(text=label, callback_data=PickAlbum(v=v, index=i))
        kb.button(text="✖ Отмена", callback_data=Action(v=v, name="cancel"))
        kb.adjust(1)
        return kb.as_markup()

    @staticmethod
    def _confirm_kb(v: int):
        kb = InlineKeyboardBuilder()
        kb.button(text="✅ Да, собрать", callback_data=Action(v=v, name="confirm"))
        kb.button(text="↩️ Другой вариант", callback_data=Action(v=v, name="back"))
        kb.button(text="✖ Отмена", callback_data=Action(v=v, name="cancel"))
        kb.adjust(1, 2)
        return kb.as_markup()

    @staticmethod
    def _back_kb(v: int):
        kb = InlineKeyboardBuilder()
        kb.button(text="↩️ Другой вариант", callback_data=Action(v=v, name="back"))
        return kb.as_markup()


async def _safe_edit(message: Message, text: str, reply_markup=None) -> None:
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as exc:  # «message is not modified» и т.п.
        log.debug("edit failed: %s", exc)
