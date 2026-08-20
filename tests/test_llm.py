"""Tests for the LLM provider adapter (OpenCode Zen / OpenAI-compatible).

These tests never hit the network — they mock the underlying HTTP client.
"""
import os
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from factory.llm import LLMClient, resolve_zen_key
from factory.model_router import ModelRouter, ModelSpec
from factory.config import Settings


def _write_auth(tmp_path: Path, key: str = "sk-test123") -> Path:
    p = tmp_path / "auth.json"
    p.write_text(json.dumps({"opencode": {"type": "api", "key": key}}))
    return p


@pytest.mark.asyncio
async def test_default_endpoint_and_model():
    """Adapter points at the OpenCode Zen gateway with big-pickle by default."""
    with patch.dict(os.environ, {}, clear=True):
        # ensure no inherited env leaks
        os.environ.pop("OPENCODE_ZEN_BASE_URL", None)
        os.environ.pop("OPENCODE_ZEN_MODEL", None)
        client = LLMClient()
        assert client.base_url == "https://opencode.ai/zen/v1"
        assert client.default_model == "opencode/big-pickle"


@pytest.mark.asyncio
async def test_key_from_env(tmp_path: Path):
    auth = _write_auth(tmp_path, "sk-envpriority")
    with patch.dict(os.environ, {"OPENCODE_ZEN_KEY": "sk-fromenv", "OPENCODE_ZEN_AUTH_PATH": str(auth)}):
        # env key wins over auth file
        assert resolve_zen_key() == "sk-fromenv"


@pytest.mark.asyncio
async def test_key_from_auth_file(tmp_path: Path):
    auth = _write_auth(tmp_path)
    with patch.dict(os.environ, {}, clear=True):
        os.environ.pop("OPENCODE_ZEN_KEY", None)
        assert resolve_zen_key(auth_path=auth) == "sk-test123"


@pytest.mark.asyncio
async def test_complete_returns_content_and_uses_model(tmp_path: Path):
    auth = _write_auth(tmp_path)
    with patch.dict(os.environ, {"OPENCODE_ZEN_AUTH_PATH": str(auth), "OPENCODE_ZEN_KEY": "sk-x"}):
        client = LLMClient()
        fake_msg = MagicMock()
        fake_msg.choices = [MagicMock(message=MagicMock(content="hello world"))]
        with patch.object(client, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=fake_msg)
            out = await client.complete([{"role": "user", "content": "hi"}], model="opencode/big-pickle")
        assert out == "hello world"
        # verify the call used the requested model
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "opencode/big-pickle"
        assert call_kwargs["messages"][0]["content"] == "hi"


@pytest.mark.asyncio
async def test_model_router_spec():
    """ModelRouter maps task types to model classes (mirrors architecture doc)."""
    from factory.model_router import ModelRouter
    router = ModelRouter(default_model="opencode/big-pickle")
    assert router.select("planning").model_class == "reasoning"
    assert router.select("coding").model_class == "coding"
    assert router.select("routing").model_class == "fast"


@pytest.mark.asyncio
async def test_retry_on_transient_error(tmp_path: Path):
    auth = _write_auth(tmp_path)
    with patch.dict(os.environ, {"OPENCODE_ZEN_AUTH_PATH": str(auth), "OPENCODE_ZEN_KEY": "sk-x"}):
        client = LLMClient()
        fake_msg = MagicMock()
        fake_msg.choices = [MagicMock(message=MagicMock(content="ok"))]
        with patch.object(client, "_client") as mock_client:
            create = AsyncMock(side_effect=[RuntimeError("transient"), fake_msg])
            mock_client.chat.completions.create = create
            out = await client.complete([{"role": "user", "content": "x"}], max_retries=2)
        assert out == "ok"
        assert create.call_count == 2
