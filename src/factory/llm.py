"""LLM provider adapter.

Primary provider: OpenCode Zen gateway (OpenAI-compatible). Optional secondary:
Hermes/Nous (`tencent/hy3:free`). Key resolution never hard-codes secrets —
it reads from `~/.local/share/opencode/auth.json` (Zen) or
`~/.hermes/auth.json` (Nous). The adapter strips the `opencode/` provider
prefix because the raw Zen HTTP API expects the bare model id.
"""
from __future__ import annotations

import asyncio
from typing import Any, Optional, Sequence

from factory.providers import ProviderConfig, get_provider


def build_client(provider: str = "nous", client: Any = None) -> "LLMClient":
    """Create an LLMClient for a named provider (nous | zen).

    Default is `nous` (Hermes/Nous `tencent/hy3:free`) because the Zen
    `big-pickle` free tier is intermittently rate-limited. `big-pickle` remains
    available via provider="zen".
    """
    cfg = get_provider(provider)
    if not cfg.api_key:
        raise RuntimeError(f"No API key resolved for provider {provider!r}")
    return LLMClient(base_url=cfg.base_url, default_model=cfg.default_model, api_key=cfg.api_key, client=client)


class LLMClient:
    """Thin async wrapper over an OpenAI-compatible chat completions API."""

    def __init__(
        self,
        base_url: str,
        default_model: str,
        api_key: str,
        client: Any = None,
    ) -> None:
        self.base_url = base_url
        self.default_model = default_model
        self._api_key = api_key
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
        # The OpenCode CLI uses names like "opencode/big-pickle", but the raw
        # Zen HTTP API expects the bare model id ("big-pickle"). Strip only the
        # "opencode/" provider prefix; other providers (e.g. "tencent/hy3:free"
        # on Nous) need the full id.
        if model.startswith("opencode/"):
            model = model[len("opencode/"):]
        last_err: Optional[Exception] = None
        for attempt in range(1, max_retries + 1):
            try:
                resp = await self.client.chat.completions.create(
                    model=model,
                    messages=list(messages),
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                msg = resp.choices[0].message
                # Some reasoning models return text in `reasoning_content`
                # instead of `content`; support both.
                content = getattr(msg, "content", None) or ""
                if not content:
                    content = getattr(msg, "reasoning_content", None) or ""
                return content
            except Exception as exc:  # transient network/API errors
                last_err = exc
                if attempt >= max_retries:
                    break
                await asyncio.sleep(backoff * attempt)
        raise RuntimeError(f"LLM call failed after {max_retries} attempts: {last_err}")
