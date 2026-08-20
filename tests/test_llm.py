"""Tests for the LLM provider adapter (OpenCode Zen / OpenAI-compatible).

These tests never hit the network — they mock the underlying HTTP client or
inject a fake client via build_client(provider, client=...).
"""
import os
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from factory.llm import LLMClient, build_client
from factory.model_router import ModelRouter, ModelSpec
from factory.providers import ProviderConfig


def _write_auth(tmp_path: Path, key: str = "sk-test123") -> Path:
    p = tmp_path / "auth.json"
    p.write_text(json.dumps({"opencode": {"type": "api", "key": key}}))
    return p


@pytest.mark.asyncio
async def test_prefix_stripped_for_bare_model_id():
    """Zen HTTP API wants bare id ('big-pickle'), not 'opencode/big-pickle'."""
    client = LLMClient(base_url="https://x", default_model="big-pickle", api_key="k")
    fake = MagicMock()
    fake.choices = [MagicMock(message=MagicMock(content="hi", reasoning_content=None))]
    with patch.object(client, "_client") as mc:
        mc.chat.completions.create = AsyncMock(return_value=fake)
        await client.complete([{"role": "user", "content": "x"}], model="opencode/big-pickle")
        assert mc.chat.completions.create.call_args.kwargs["model"] == "big-pickle"


@pytest.mark.asyncio
async def test_reasoning_content_fallback():
    """Reasoning models may return text in reasoning_content, not content."""
    client = LLMClient(base_url="https://x", default_model="big-pickle", api_key="k")
    fake = MagicMock()
    fake.choices = [MagicMock(message=MagicMock(content=None, reasoning_content="thought"))]
    with patch.object(client, "_client") as mc:
        mc.chat.completions.create = AsyncMock(return_value=fake)
        out = await client.complete([{"role": "user", "content": "x"}])
    assert out == "thought"


@pytest.mark.asyncio
async def test_build_client_zen_uses_auth_file(tmp_path: Path):
    auth = _write_auth(tmp_path, "sk-fromfile")
    with patch.dict(os.environ, {}, clear=True):
        os.environ["OPENCODE_ZEN_AUTH_PATH"] = str(auth)
        os.environ.pop("OPENCODE_ZEN_KEY", None)
        client = build_client("zen", client=MagicMock())
    assert client.default_model == "big-pickle"
    assert client._api_key == "sk-fromfile"


@pytest.mark.asyncio
async def test_build_client_nous():
    client = build_client("nous", client=MagicMock())
    assert client.base_url.endswith("nousresearch.com/v1") or "nous" in client.base_url
    assert client.default_model == "tencent/hy3:free"


@pytest.mark.asyncio
async def test_model_router_spec():
    """ModelRouter maps task types to model classes (mirrors architecture doc)."""
    router = ModelRouter(default_model="tencent/hy3:free")
    assert router.select("planning").model_class == "reasoning"
    assert router.select("coding").model_class == "coding"
    assert router.select("routing").model_class == "fast"
    # concrete model is the provider default, not a hardcoded name
    assert router.select("planning").model == "tencent/hy3:free"


@pytest.mark.asyncio
async def test_retry_on_transient_error():
    client = LLMClient(base_url="https://x", default_model="big-pickle", api_key="k")
    fake = MagicMock()
    fake.choices = [MagicMock(message=MagicMock(content="ok"))]
    with patch.object(client, "_client") as mc:
        create = AsyncMock(side_effect=[RuntimeError("transient"), fake])
        mc.chat.completions.create = create
        out = await client.complete([{"role": "user", "content": "x"}], max_retries=2)
    assert out == "ok"
    assert create.call_count == 2
