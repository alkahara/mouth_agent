"""Retrieval helpers that combine semantic and keyword indices."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from langchain_community.retrievers import BM25Retriever
from langchain_community.vectorstores import FAISS

DEFAULT_RETRIEVAL_TOP_K = 10


@dataclass
class HybridVectorRetriever:
    """Wrapper that blends FAISS semantic search with BM25 keyword search."""

    semantic_store: FAISS
    keyword_retriever: BM25Retriever
    semantic_weight: float = 0.6
    keyword_weight: float = 0.4

    def __post_init__(self) -> None:
        if self.semantic_weight <= 0 and self.keyword_weight <= 0:
            raise ValueError("语义检索与关键词检索的权重不能同时为 0。")
        total = self.semantic_weight + self.keyword_weight
        self._weights = [self.semantic_weight / total, self.keyword_weight / total]

    def as_retriever(self, *, search_kwargs: Dict[str, Any] | None = None):
        """Return an ensemble retriever combining semantic and keyword search."""
        from langchain.retrievers.ensemble import EnsembleRetriever

        if search_kwargs is None:
            search_kwargs = {"k": DEFAULT_RETRIEVAL_TOP_K}
        else:
            search_kwargs = dict(search_kwargs)
            search_kwargs.setdefault("k", DEFAULT_RETRIEVAL_TOP_K)

        semantic_kwargs = dict(search_kwargs)
        semantic_retriever = self.semantic_store.as_retriever(search_kwargs=semantic_kwargs)

        if "k" in search_kwargs and hasattr(self.keyword_retriever, "k"):
            self.keyword_retriever.k = search_kwargs["k"]

        return EnsembleRetriever(
            retrievers=[semantic_retriever, self.keyword_retriever],
            weights=self._weights,
        )

    def __getattr__(self, item: str) -> Any:  # pragma: no cover - passthrough helper
        return getattr(self.semantic_store, item)


__all__ = ["HybridVectorRetriever", "DEFAULT_RETRIEVAL_TOP_K"]
