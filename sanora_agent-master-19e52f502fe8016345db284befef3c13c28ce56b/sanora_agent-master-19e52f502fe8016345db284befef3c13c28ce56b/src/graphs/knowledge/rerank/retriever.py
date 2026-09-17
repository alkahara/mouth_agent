"""Retriever wrapper that applies reranking on top of base results."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Sequence

from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import ConfigDict

from .providers import BaseReranker

logger = logging.getLogger(__name__)


class RerankRetriever(BaseRetriever):
    """Augments an existing retriever with rerank capability."""

    base_retriever: BaseRetriever
    reranker: BaseReranker | Any
    top_k: int | None = None
    model_config = ConfigDict(arbitrary_types_allowed=True)

    def __init__(
        self,
        *,
        base_retriever: BaseRetriever,
        reranker: BaseReranker,
        top_k: int | None = None,
    ) -> None:
        super().__init__(
            base_retriever=base_retriever,
            reranker=reranker,
            top_k=top_k,
        )

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager=None,
    ) -> Sequence[Document]:  # type: ignore[override]
        candidates = self._fetch_candidates(query)
        return self._apply_rerank(query, candidates)

    async def _aget_relevant_documents(
        self,
        query: str,
        *,
        run_manager=None,
    ) -> Sequence[Document]:  # type: ignore[override]
        candidates = await self._afetch_candidates(query)
        return await self._aapply_rerank(query, candidates)

    def _fetch_candidates(self, query: str) -> Sequence[Document]:
        try:
            # Try invoke first (newer API)
            if hasattr(self.base_retriever, "invoke"):
                logger.debug("RerankRetriever: using base_retriever.invoke")
                print("RerankRetriever: using base_retriever.invoke")
                return self.base_retriever.invoke(query)  # type: ignore[call-arg]
            # Fallback to get_relevant_documents
            if hasattr(self.base_retriever, "get_relevant_documents"):
                logger.debug("RerankRetriever: using base_retriever.get_relevant_documents")
                print("RerankRetriever: using base_retriever.get_relevant_documents")
                return self.base_retriever.get_relevant_documents(query)  # type: ignore[attr-defined]
            # Last resort: use internal method
            logger.debug("RerankRetriever: falling back to base_retriever._get_relevant_documents")
            print("RerankRetriever: falling back to base_retriever._get_relevant_documents")
            return self.base_retriever._get_relevant_documents(query)  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Base retriever failed to fetch candidates: %s", exc)
            return []

    async def _afetch_candidates(self, query: str) -> Sequence[Document]:
        # Try ainvoke first (newer API)
        if hasattr(self.base_retriever, "ainvoke"):
            try:
                logger.debug("RerankRetriever: using base_retriever.ainvoke")
                print("RerankRetriever: using base_retriever.ainvoke")
                return await self.base_retriever.ainvoke(query)  # type: ignore[call-arg]
            except Exception as exc:  # pragma: no cover - defensive
                logger.exception("Async base retriever .ainvoke failed: %s", exc)
                return []
        # Fallback to aget_relevant_documents
        if hasattr(self.base_retriever, "aget_relevant_documents"):
            try:
                logger.debug("RerankRetriever: using base_retriever.aget_relevant_documents")
                print("RerankRetriever: using base_retriever.aget_relevant_documents")
                return await self.base_retriever.aget_relevant_documents(query)  # type: ignore[call-arg]
            except Exception as exc:  # pragma: no cover - defensive
                logger.exception("Async base retriever failed: %s", exc)
                return []
        # Last resort: use sync method in thread pool
        logger.debug("RerankRetriever: async fallback via thread pool")
        print("RerankRetriever: async fallback via thread pool")
        return await asyncio.to_thread(self._fetch_candidates, query)

    @staticmethod
    def _summarize_document(
        documents: Sequence[Document],
        *,
        snippet: int = 120,
    ) -> dict[str, str] | None:
        if not documents:
            return None
        doc = documents[0]
        metadata = getattr(doc, "metadata", {}) or {}
        doc_id = (
            metadata.get("id")
            or metadata.get("document_id")
            or metadata.get("source")
            or "doc-0"
        )
        content = (doc.page_content or "").replace("\n", " ")
        summary: dict[str, str] = {"id": str(doc_id), "snippet": content[:snippet]}
        score = metadata.get("rerank_score")
        if score is not None:
            summary["score"] = str(score)
        return summary

    def _apply_rerank(
        self,
        query: str,
        documents: Sequence[Document],
    ) -> Sequence[Document]:
        if not documents:
            return documents
        candidates_summary = self._summarize_document(documents)
        logger.info(
            "Rerank input | top_k=%s | candidate_count=%s | first_candidate=%s",
            self.top_k,
            len(documents),
            candidates_summary,
        )
        try:
            reranked = self.reranker.rerank(query, documents, top_k=self.top_k)
            if reranked:
                result_summary = self._summarize_document(reranked)
                logger.info(
                    "Rerank output | top_k=%s | returned_count=%s | first_result=%s",
                    self.top_k,
                    len(reranked),
                    result_summary,
                )
                return reranked
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Rerank failed, falling back to original order: %s", exc)
        limit = self.top_k or len(documents)
        return list(documents[:limit])

    async def _aapply_rerank(
        self,
        query: str,
        documents: Sequence[Document],
    ) -> Sequence[Document]:
        if not documents:
            return documents
        candidates_summary = self._summarize_document(documents)
        logger.info(
            "Rerank input | top_k=%s | candidate_count=%s | first_candidate=%s",
            self.top_k,
            len(documents),
            candidates_summary,
        )
        try:
            reranked = await asyncio.to_thread(
                self.reranker.rerank,
                query,
                documents,
                top_k=self.top_k,
            )
            if reranked:
                result_summary = self._summarize_document(reranked)
                logger.info(
                    "Rerank output | top_k=%s | returned_count=%s | first_result=%s",
                    self.top_k,
                    len(reranked),
                    result_summary,
                )
                return reranked
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Async rerank failed, falling back: %s", exc)
        limit = self.top_k or len(documents)
        return list(documents[:limit])


__all__ = ["RerankRetriever"]
