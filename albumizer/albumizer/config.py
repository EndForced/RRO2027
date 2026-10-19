"""Настройки из переменных окружения (.env поддерживается)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_SOURCES = (
    "youtube_full",       # полный альбом одним видео на YouTube
    "ytmusic_album",      # официальный альбом-плейлист YouTube Music
    "bandcamp",
    "archive_org",
    "youtube_tracks",     # каждый трек отдельно на YouTube
    "soundcloud_tracks",
)


@dataclass(frozen=True)
class LLMProviderConfig:
    name: str
    base_url: str
    api_key: str
    model: str


# Бесплатные тарифы (лимиты на октябрь 2026, проверяйте на сайтах провайдеров).
LLM_PRESETS = {
    "groq": ("https://api.groq.com/openai/v1", "llama-3.3-70b-versatile"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "gemini-flash-latest"),
    "openrouter": ("https://openrouter.ai/api/v1", "meta-llama/llama-3.3-70b-instruct:free"),
    "cerebras": ("https://api.cerebras.ai/v1", "llama-3.3-70b"),
    "ollama": ("http://localhost:11434/v1", "qwen2.5:7b"),
}


@dataclass(frozen=True)
class Settings:
    bot_token: str
    workdir: Path = Path("./data")
    sources: tuple[str, ...] = DEFAULT_SOURCES
    llm_providers: tuple[LLMProviderConfig, ...] = ()
    llm_judge: bool = True
    musicbrainz_user_agent: str = "Albumizer/0.1 (https://github.com/endforced/rro2027)"
    allowed_users: frozenset[int] | None = None
    max_parallel_jobs: int = 2
    download_concurrency: int = 3
    audio_quality: str = "192"
    ytdlp_cookies: str | None = None
    ytdlp_proxy: str | None = None

    @classmethod
    def from_env(cls) -> Settings:
        try:
            from dotenv import load_dotenv

            load_dotenv()
        except ImportError:
            pass
        env = os.environ
        token = env.get("BOT_TOKEN", "")
        if not token:
            raise RuntimeError("BOT_TOKEN is not set")
        users = {int(u) for u in _list(env.get("ALLOWED_USERS"))}
        return cls(
            bot_token=token,
            workdir=Path(env.get("WORKDIR", "./data")),
            sources=tuple(_list(env.get("SOURCES"))) or DEFAULT_SOURCES,
            llm_providers=tuple(_llm_providers(env)),
            llm_judge=env.get("LLM_JUDGE", "1") not in ("0", "false", "no"),
            musicbrainz_user_agent=env.get("MUSICBRAINZ_USER_AGENT", cls.musicbrainz_user_agent),
            allowed_users=frozenset(users) if users else None,
            max_parallel_jobs=int(env.get("MAX_PARALLEL_JOBS", "2")),
            download_concurrency=int(env.get("DOWNLOAD_CONCURRENCY", "3")),
            audio_quality=env.get("AUDIO_QUALITY", "192"),
            ytdlp_cookies=env.get("YTDLP_COOKIES") or None,
            ytdlp_proxy=env.get("YTDLP_PROXY") or None,
        )


def _list(value: str | None) -> list[str]:
    return [x.strip() for x in (value or "").split(",") if x.strip()]


def _llm_providers(env: os._Environ[str] | dict[str, str]) -> list[LLMProviderConfig]:
    """LLM_PROVIDERS=groq,gemini — порядок = порядок failover.
    Для каждого: <NAME>_API_KEY, опционально <NAME>_MODEL и <NAME>_BASE_URL."""
    result = []
    for name in _list(env.get("LLM_PROVIDERS")):
        key = name.upper()
        preset_url, preset_model = LLM_PRESETS.get(name.lower(), ("", ""))
        api_key = env.get(f"{key}_API_KEY", "ollama" if name.lower() == "ollama" else "")
        base_url = env.get(f"{key}_BASE_URL", preset_url)
        model = env.get(f"{key}_MODEL", preset_model)
        if api_key and base_url and model:
            result.append(LLMProviderConfig(name, base_url, api_key, model))
    return result
