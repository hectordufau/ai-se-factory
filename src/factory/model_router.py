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


# Default policy. All roles use the provider's default model (passed to the
# router). The "model judgment" dimension (reasoning vs coding vs fast) is
# expressed via model_class + temperature; swapping which concrete model backs
# each class is a one-line provider change (e.g. big-pickle vs tencent/hy3:free).
_DEFAULT_POLICY: dict[str, tuple[str, float, int]] = {
    "planning": ("reasoning", 0.3, 8192),
    "architecture": ("reasoning", 0.3, 8192),
    "coding": ("coding", 0.2, 8192),
    "testing": ("coding", 0.1, 4096),
    "routing": ("fast", 0.0, 1024),
    "security": ("reasoning", 0.2, 4096),
    "review": ("reasoning", 0.2, 4096),
}


class ModelRouter:
    def __init__(
        self,
        default_model: str = "tencent/hy3:free",
        policy: Optional[dict[str, ModelSpec]] = None,
    ) -> None:
        self.default_model = default_model
        self._policy = policy or self._build_policy(default_model)

    @staticmethod
    def _build_policy(default_model: str) -> dict[str, ModelSpec]:
        return {
            task: ModelSpec(model=default_model, model_class=cls, temperature=temp, max_tokens=mt)
            for task, (cls, temp, mt) in _DEFAULT_POLICY.items()
        }

    def select(self, task_type: str) -> ModelSpec:
        return self._policy.get(task_type, ModelSpec(self.default_model, "coding"))

    async def complete_for_task(
        self, client: "LLMClient", task_type: str, messages, **kwargs
    ) -> str:
        spec = self.select(task_type)
        return await client.complete(
            messages,
            model=spec.model,
            temperature=kwargs.pop("temperature", spec.temperature),
            max_tokens=kwargs.pop("max_tokens", spec.max_tokens),
            **kwargs,
        )
