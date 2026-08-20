"""Model router — maps task types to model classes (model judgment).

Mirrors the architecture note: reasoning models for planning/architecture,
coding models for implementation, fast models for routing/classification.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from factory.llm import LLMClient


@dataclass(frozen=True)
class ModelSpec:
    model: str
    model_class: str  # "reasoning" | "coding" | "fast"
    temperature: float = 0.2
    max_tokens: int = 4096


# Default policy. The primary model is opencode/big-pickle (OpenCode Zen).
# For model-judgment demos, override per task type with a secondary provider.
_DEFAULT_POLICY: dict[str, ModelSpec] = {
    "planning": ModelSpec("opencode/big-pickle", "reasoning", 0.3, 8192),
    "architecture": ModelSpec("opencode/big-pickle", "reasoning", 0.3, 8192),
    "coding": ModelSpec("opencode/big-pickle", "coding", 0.2, 8192),
    "testing": ModelSpec("opencode/big-pickle", "coding", 0.1, 4096),
    "routing": ModelSpec("opencode/big-pickle", "fast", 0.0, 1024),
    "security": ModelSpec("opencode/big-pickle", "reasoning", 0.2, 4096),
    "review": ModelSpec("opencode/big-pickle", "reasoning", 0.2, 4096),
}


class ModelRouter:
    def __init__(
        self,
        default_model: str = "opencode/big-pickle",
        policy: Optional[dict[str, ModelSpec]] = None,
    ) -> None:
        self.default_model = default_model
        self._policy = policy or dict(_DEFAULT_POLICY)

    def select(self, task_type: str) -> ModelSpec:
        return self._policy.get(task_type, ModelSpec(self.default_model, "coding"))

    async def complete_for_task(
        self, client: LLMClient, task_type: str, messages, **kwargs
    ) -> str:
        spec = self.select(task_type)
        return await client.complete(
            messages,
            model=spec.model,
            temperature=kwargs.pop("temperature", spec.temperature),
            max_tokens=kwargs.pop("max_tokens", spec.max_tokens),
            **kwargs,
        )
