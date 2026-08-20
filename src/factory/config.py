"""Configuration / settings resolution for the factory.

Reads from env, with sane defaults. Never hard-codes secrets.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Resolved runtime settings."""

    zen_base_url: str
    zen_model: str
    zen_auth_path: Path
    zen_key_env: str = "OPENCODE_ZEN_KEY"
    log_level: str = "INFO"

    @property
    def default_base_url(self) -> str:
        return self.zen_base_url

    @property
    def default_model(self) -> str:
        return self.zen_model


def _default_auth_path() -> Path:
    candidates = [
        Path(os.environ.get("OPENCODE_ZEN_AUTH_PATH", "")).expanduser()
        if os.environ.get("OPENCODE_ZEN_AUTH_PATH")
        else None,
        Path.home() / ".local" / "share" / "opencode" / "auth.json",
        Path.home() / ".opencode" / "auth.json",
    ]
    for c in candidates:
        if c and c.exists():
            return c
    # fallback to first candidate path even if missing (resolved lazily)
    return candidates[1]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        zen_base_url=os.environ.get("OPENCODE_ZEN_BASE_URL", "https://opencode.ai/zen/v1"),
        zen_model=os.environ.get("OPENCODE_ZEN_MODEL", "opencode/big-pickle"),
        zen_auth_path=_default_auth_path(),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
    )
