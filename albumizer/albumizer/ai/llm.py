"""Клиенты LLM.

Используется OpenAI-совместимый протокол /chat/completions — его поддерживают
Groq, Google Gemini (через /v1beta/openai), OpenRouter, Cerebras и локальный Ollama.
Поэтому провайдер меняется одной строкой в .env, без изменений кода.
"""
from __future__ import annotations

import json
import logging
import re
from collections.abc import Sequence
from typing import Any

import httpx

from ..interfaces import LLMClient

log = logging.getLogger(__name__)


class LLMError(RuntimeError):
    pass


class OpenAICompatibleLLM:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        *,
        timeout: float = 30.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._model = model
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._client = client or httpx.AsyncClient(timeout=timeout)

    async def complete(self, system: str, user: str) -> str:
        payload = {
            "model": self._model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        try:
            resp = await self._client.post(self._url, json=payload, headers=self._headers)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"] or ""
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            raise LLMError(f"{self._model}: {exc}") from exc


class FailoverLLM:
    """Перебирает клиентов по очереди — полезно при лимитах бесплатных тарифов."""

    def __init__(self, clients: Sequence[LLMClient]) -> None:
        if not clients:
            raise ValueError("FailoverLLM needs at least one client")
        self._clients = list(clients)

    async def complete(self, system: str, user: str) -> str:
        last: Exception | None = None
        for client in self._clients:
            try:
                return await client.complete(system, user)
            except LLMError as exc:
                log.warning("LLM failover: %s", exc)
                last = exc
        raise LLMError(f"all LLM providers failed: {last}")


_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def extract_json(text: str) -> dict[str, Any]:
    """Достаёт первый JSON-объект из ответа модели (модели любят ```json обёртки)."""
    match = _JSON_BLOCK.search(text)
    if not match:
        raise LLMError(f"no JSON in LLM answer: {text[:200]!r}")
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise LLMError(f"bad JSON in LLM answer: {exc}") from exc
    if not isinstance(data, dict):
        raise LLMError("LLM answer is not a JSON object")
    return data
