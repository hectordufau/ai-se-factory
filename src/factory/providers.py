"""Provider configuration for the factory LLM clients.

Primary: OpenCode Zen (`opencode/big-pickle`) — generous free tier.
Optional: Hermes/Nous (`tencent/hy3:free`) — comparison / fallback.
Both are OpenAI-compatible. Keys are resolved from local auth files, never
hard-coded.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    base_url: str
    api_key: str
    default_model: str


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def zen_config() -> ProviderConfig:
    """OpenCode Zen gateway. Model `big-pickle` (prefix stripped at call time)."""
    env_path = os.environ.get("OPENCODE_ZEN_AUTH_PATH", "")
    auth_path = Path(env_path).expanduser() if env_path else Path.home() / ".local" / "share" / "opencode" / "auth.json"
    key = os.environ.get("OPENCODE_ZEN_KEY") or _read_json(auth_path).get("opencode", {}).get("key", "")
    return ProviderConfig(
        name="zen",
        base_url=os.environ.get("OPENCODE_ZEN_BASE_URL", "https://opencode.ai/zen/v1"),
        api_key=key,
        default_model=os.environ.get("OPENCODE_ZEN_MODEL", "big-pickle"),
    )


def nous_config() -> ProviderConfig:
    """Hermes/Nous inference API. Model `tencent/hy3:free`."""
    auth_path = Path.home() / ".hermes" / "auth.json"
    data = _read_json(auth_path)
    token = data.get("providers", {}).get("nous", {}).get("access_token", "")
    base = data.get("providers", {}).get("nous", {}).get(
        "inference_base_url", "https://inference-api.nousresearch.com/v1"
    )
    return ProviderConfig(
        name="nous",
        base_url=os.environ.get("NOUS_BASE_URL", base),
        api_key=os.environ.get("NOUS_API_KEY", token),
        default_model=os.environ.get("NOUS_MODEL", "tencent/hy3:free"),
    )


def get_provider(name: str = "zen") -> ProviderConfig:
    return nous_config() if name == "nous" else zen_config()
