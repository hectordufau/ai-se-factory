"""LLM provider adapter.

Primary provider: OpenCode Zen gateway (OpenAI-compatible). Defaults to
`opencode/big-pickle`. Key resolution: env `OPENCODE_ZEN_KEY` -> auth.json
(`~/.local/share/opencode/auth.json`). Never hard-codes secrets.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any, Optional, Sequence

from factory.config import Settings, get_settings


def resolve_zen_key(
    settings: Optional[Settings] = None,
    auth_path: Optional[Path] = None,
) -> str:
    """Resolve the OpenCode Zen API key.

    Priority: OPENCODE_ZEN_KEY env -> `opencode.key` in auth.json.
    `auth_path` allows tests to inject a path without touching global settings.
    Raises a clear error if neither is available.
    """
    settings = settings or get_settings()
    env_key = os.environ.get("OPENCODE_ZEN_KEY")
    if env_key:
        return env_key
    auth_path = auth_path or settings.zen_auth_path
    if auth_path.exists():
        try:
            data = json.loads(auth_path.read_text())
            key = data.get("opencode", {}).get("key")
            if key:
                return key
        except (json.JSONDecodeError, OSError):
            pass
    raise RuntimeError(
        "OpenCode Zen key not found. Set OPENCODE_ZEN_KEY or ensure "
        f"{auth_path} contains {{\"opencode\": {{\"type\": \"api\", \"key\": ...}}}}"
    )


class LLMClient:
    """Thin async wrapper over an OpenAI-compatible chat completions API."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        api_key: Optional[str] = None,
        client: Any = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.base_url = self.settings.zen_base_url
        self.default_model = self.settings.zen_model
        self._api_key = api_key or resolve_zen_key(self.settings)
        # `client` is injectable for tests; otherwise lazily created.
        self._client = client

    @property
    def client(self):
        if self._client is None:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(
                base_url=self.base_url,
                api_key=self._api_key,
            )
        return self._client

    async def complete(
        self,
        messages: Sequence[dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        max_retries: int = 3,
        backoff: float = 0.5,
    ) -> str:
        """Return the assistant message content for a chat completion."""
        model = model or self.default_model
        last_err: Optional[Exception] = None
        for attempt in range(1, max_retries + 1):
            try:
                resp = await self.client.chat.completions.create(
                    model=model,
                    messages=list(messages),
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return resp.choices[0].message.content or ""
            except Exception as exc:  # transient network/API errors
                last_err = exc
                if attempt >= max_retries:
                    break
                await asyncio.sleep(backoff * attempt)
        raise RuntimeError(f"LLM call failed after {max_retries} attempts: {last_err}")
