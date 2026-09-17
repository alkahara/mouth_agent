"""Provider-specific reranker implementations."""

from __future__ import annotations

import json
import logging
import os
from typing import Mapping, Protocol, Sequence, runtime_checkable

import httpx
from langchain_core.documents import Document

from .config import RerankConfig

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 15.0


@runtime_checkable
class BaseReranker(Protocol):
    """Common interface for reranker implementations."""

    def rerank(
        self,
        query: str,
        documents: Sequence[Document],
        *,
        top_k: int | None = None,
    ) -> Sequence[Document]:
        """Return documents ordered by relevance for the given query."""


class JinaReranker:
    """Jina AI Cloud reranker implementation."""

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        endpoint: str | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
        extra_headers: Mapping[str, str] | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("Jina API key is required for reranking.")
        if not model:
            raise ValueError("Jina rerank model name must be provided.")

        self.model = model
        self.timeout = timeout
        self.endpoint = endpoint or "https://api.jina.ai/v1/rerank"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        if extra_headers:
            headers.update(dict(extra_headers))
        self.headers = headers

    def rerank(
        self,
        query: str,
        documents: Sequence[Document],
        *,
        top_k: int | None = None,
    ) -> Sequence[Document]:
        if not documents:
            return []

        limit = top_k or len(documents)
        payload = {
            "model": self.model,
            "query": query,
            "top_n": max(1, min(limit, len(documents))),
            "documents": [doc.page_content for doc in documents],
        }

        try:
            response = httpx.post(
                self.endpoint,
                headers=self.headers,
                content=json.dumps(payload, ensure_ascii=False),
                timeout=self.timeout,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:  # pragma: no cover
            body = exc.response.text if exc.response is not None else ""
            logger.warning(
                "Jina rerank request failed (%s): %s",
                exc.response.status_code if exc.response else "?",
                body[:500],
            )
            raise

        data = response.json()
        results = data.get("results") if isinstance(data, dict) else None
        if not results and isinstance(data, dict):
            results = data.get("data")
        if not results:
            logger.warning("Unexpected Jina rerank response: %s", data)
            return list(documents[:limit])

        indexed: list[tuple[int, float]] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            idx = item.get("index")
            score = item.get("score") or item.get("relevance_score")
            if idx is None or score is None:
                continue
            try:
                idx = int(idx)
                score = float(score)
            except (TypeError, ValueError):
                continue
            indexed.append((idx, score))

        if not indexed:
            return list(documents[:limit])

        indexed.sort(key=lambda pair: pair[1], reverse=True)

        reordered: list[Document] = []
        for doc_index, score in indexed[:limit]:
            if doc_index >= len(documents):
                continue
            doc = documents[doc_index]
            metadata = dict(doc.metadata)
            metadata["rerank_score"] = score
            metadata["rerank_model"] = self.model
            reordered.append(Document(page_content=doc.page_content, metadata=metadata))

        if not reordered:
            return list(documents[:limit])
        return reordered


class BGEReranker:
    """BGE reranker hosted behind a compatible REST endpoint."""

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        endpoint: str | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
        extra_headers: Mapping[str, str] | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("BGE rerank API key is required.")
        if not model:
            raise ValueError("BGE rerank model name must be provided.")

        self.model = model
        self.timeout = timeout
        self.endpoint = endpoint or "http://47.93.78.21:28800/v1/rerank"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        if extra_headers:
            headers.update(dict(extra_headers))
        self.headers = headers

    def rerank(
        self,
        query: str,
        documents: Sequence[Document],
        *,
        top_k: int | None = None,
    ) -> Sequence[Document]:
        if not documents:
            return []

        limit = top_k or len(documents)
        payload = {
            "model": self.model,
            "query": query,
            "top_n": max(1, min(limit, len(documents))),
            "documents": [doc.page_content for doc in documents],
        }

        try:
            response = httpx.post(
                self.endpoint,
                headers=self.headers,
                content=json.dumps(payload, ensure_ascii=False),
                timeout=self.timeout,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:  # pragma: no cover
            body = exc.response.text if exc.response is not None else ""
            logger.warning(
                "BGE rerank request failed (%s): %s",
                exc.response.status_code if exc.response else "?",
                body[:500],
            )
            raise

        data = response.json()
        results = None
        if isinstance(data, dict):
            results = data.get("results") or data.get("data")
        if not results:
            logger.warning("Unexpected BGE rerank response: %s", data)
            return list(documents[:limit])

        indexed: list[tuple[int, float]] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            idx = item.get("index")
            score = item.get("score") or item.get("relevance_score")
            if idx is None or score is None:
                continue
            try:
                idx = int(idx)
                score = float(score)
            except (TypeError, ValueError):
                continue
            indexed.append((idx, score))

        if not indexed:
            return list(documents[:limit])

        indexed.sort(key=lambda pair: pair[1], reverse=True)

        reordered: list[Document] = []
        for doc_index, score in indexed[:limit]:
            if doc_index >= len(documents):
                continue
            doc = documents[doc_index]
            metadata = dict(doc.metadata)
            metadata["rerank_score"] = score
            metadata["rerank_model"] = self.model
            reordered.append(Document(page_content=doc.page_content, metadata=metadata))

        if not reordered:
            return list(documents[:limit])
        return reordered


def build_reranker(config: RerankConfig) -> BaseReranker | None:
    """Instantiate a reranker based on the supplied configuration."""

    provider = config.resolve_provider().lower()
    if not provider:
        return None
    model = config.resolve_model()

    timeout = config.timeout or _DEFAULT_TIMEOUT
    api_key = config.resolve_api_key()
    fallback_env = _default_api_env(provider)
    if api_key is None and fallback_env:
        for env_name in fallback_env:
            api_key = os.getenv(env_name)
            if api_key:
                break
    if api_key is None:
        logger.warning(
            "Rerank provider '%s' missing API key, skipping rerank initialization.",
            provider,
        )
        return None

    extra_headers: Mapping[str, str] | None = None
    if config.extra:
        headers = config.extra.get("headers")
        if isinstance(headers, Mapping):
            extra_headers = headers

    if provider == "jina":
        model_name = model or "jina-reranker-v2-base-multilingual"
        return JinaReranker(
            model=model_name,
            api_key=api_key,
            endpoint=config.endpoint,
            timeout=timeout,
            extra_headers=extra_headers,
        )

    if provider in {"bge", "bge-rerank", "bge_rerank"}:
        model_name = model or "bge-reranker-v2-m3"
        return BGEReranker(
            model=model_name,
            api_key=api_key,
            endpoint=config.endpoint,
            timeout=timeout,
            extra_headers=extra_headers,
        )

    raise ValueError(f"Unsupported rerank provider '{config.provider}'.")


def _default_api_env(provider: str) -> tuple[str, ...] | None:
    if provider == "jina":
        return ("JINA_RERANK_API_KEY", "JINA_API_KEY")
    if provider in {"bge", "bge-rerank", "bge_rerank"}:
        return ("BGE_RERANK_API_KEY", "GPUSTACK_API_KEY")
    return None


__all__ = [
    "BaseReranker",
    "build_reranker",
    "JinaReranker",
    "BGEReranker",
]
