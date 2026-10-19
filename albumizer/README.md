# Альбомизатор

Telegram-бот: присылаешь название альбома, бот находит треклист, ты подтверждаешь, а бот собирает альбом в mp3 с тегами и обложкой.

## Пайплайн

```
текст ─► QueryParser (LLM / эвристика) ─► MetadataProvider (Deezer + MusicBrainz)
      ─► выбор альбома и подтверждение треклиста в Telegram
      ─► SourceFinder: цепочка площадок, первая удачная побеждает
           1. youtube_full       одно видео, длина ≈ сумме треков (±max(45 c, 3 %)) + опц. проверка LLM
           2. ytmusic_album      официальный альбом-плейлист YouTube Music
           3. bandcamp           парсинг поиска + сопоставление треков
           4. archive_org        API Internet Archive
           5. youtube_tracks     каждый трек отдельно (длина ±8 c)
           6. soundcloud_tracks
      ─► Downloader (yt-dlp → mp3) ─► AudioSplitter (ffmpeg: главы видео или длины треков)
      ─► Tagger (ID3 + обложка) ─► отправка в Telegram группами по 10
```

## Архитектура (loose coupling)

Все слои общаются через протоколы из `albumizer/interfaces.py`. Конкретные классы выбираются
и связываются только в `albumizer/app.py` (composition root).

| Модуль | Ответственность |
|---|---|
| `models.py` | доменные dataclass'ы (`Album`, `Track`, `SourceMatch`…) |
| `interfaces.py` | протоколы: `MetadataProvider`, `MediaSearcher`, `PlaylistExtractor`, `SourceFinder`, `Downloader`, `AudioSplitter`, `Tagger`, `LLMClient`, `AlbumService`… |
| `matching.py` | чистые функции: сравнение длительностей и названий, стоп-слова |
| `metadata/` | Deezer, MusicBrainz, `CompositeMetadata` |
| `sources/` | стратегии: `FullAlbumVideoFinder`, `PlaylistAlbumFinder`, `PerTrackFinder`, `ChainSourceFinder`; адаптеры Bandcamp и Archive.org |
| `media/` | адаптеры yt-dlp (поиск, плейлисты, скачивание), ffmpeg-нарезка, теги mutagen |
| `ai/` | OpenAI-совместимый клиент с failover, разбор запроса, проверка «это точно альбом?» |
| `pipeline.py` | `AlbumPipeline` — фасад `AlbumService`, ничего не знает о Telegram |
| `bot/` | `AlbumBot` (aiogram 3) — знает только `AlbumService` и `SessionStore` |

Чтобы добавить площадку, реализуйте `MediaSearcher` (и при необходимости `PlaylistExtractor`),
оберните в одну из готовых стратегий и добавьте фабрику в `build_source_finder`.

## AI

AI не обязателен: без ключей работают эвристики. С AI бот понимает запросы вроде
«пинк флойд дарк сайд» и отсекает каверы и live-версии, которые совпали по длине.
Используется OpenAI-совместимый `/chat/completions`, так что провайдер меняется в `.env`:

- **Groq** — бесплатно, `llama-3.3-70b-versatile` (около 1000 запросов в день); по умолчанию.
- **Google Gemini** — бесплатный тариф Flash; на бесплатном тарифе данные могут использоваться для обучения.
- **OpenRouter** — модели с суффиксом `:free` (около 50 запросов в день без пополнения).
- **Cerebras**, **Ollama** (локально, бесплатно).

Лимиты бесплатных тарифов часто меняются, поэтому можно указать несколько провайдеров
(`LLM_PROVIDERS=groq,gemini`): при ошибке или упоре в лимит запрос уходит следующему.
На одну сборку тратится 1–3 запроса.

## Запуск

Нужны Python 3.11+ и `ffmpeg` в `PATH`.

```bash
cd albumizer
pip install -e .[dev]
cp .env.example .env   # вписать BOT_TOKEN и, по желанию, ключи AI
python -m albumizer
pytest
```

## Ограничения

- Bot API принимает файлы до 50 МБ; треки крупнее пропускаются, и бот об этом сообщает.
- YouTube иногда требует подтверждения «вы не бот»; в этом случае укажите `YTDLP_COOKIES`.
- Сессии хранятся в памяти; для нескольких инстансов реализуйте `SessionStore` на Redis.
- Скачивайте только то, на что у вас есть права.
