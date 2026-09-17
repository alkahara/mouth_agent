"""Configuration helpers for rerank integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence


class RerankProvider(str, Enum):
    """Supported rerank provider identifiers."""

    JINA = "jina"
    BGE = "bge"


@dataclass(slots=True)
class RerankConfig:
    """Runtime configuration for optional rerank steps."""

    provider: RerankProvider | str | None = None
    model: str | None = None
    model_env: str | None = None
    api_key: str | None = None
    api_key_env: str | None = None
    endpoint: str | None = None
    top_k: int | None = None
    candidate_k: int | None = None
    timeout: float | None = None
    extra: Mapping[str, Any] = field(default_factory=dict)
    fallback_envs: Sequence[str] = field(default_factory=tuple)

    def resolve_api_key(self) -> str | None:
        """Return the first available API key from explicit or environment sources."""

        if self.api_key:
            return self.api_key

        if self.api_key_env:
            import os

            value = os.getenv(self.api_key_env)
            if value:
                return value

        if self.fallback_envs:
            import os

            for env_name in self.fallback_envs:
                value = os.getenv(env_name)
                if value:
                    return value

        return None

    def resolve_model(self) -> str | None:
        """Resolve the model identifier, honoring environment overrides."""

        if self.model:
            return self.model

        if self.model_env:
            import os

            value = os.getenv(self.model_env)
            if value:
                return value

        return None

    def resolve_provider(self) -> str:
        """Return the normalized provider identifier."""

        if isinstance(self.provider, RerankProvider):
            return self.provider.value
        if isinstance(self.provider, str):
            return self.provider
        return ""


__all__ = ["RerankConfig", "RerankProvider"]
