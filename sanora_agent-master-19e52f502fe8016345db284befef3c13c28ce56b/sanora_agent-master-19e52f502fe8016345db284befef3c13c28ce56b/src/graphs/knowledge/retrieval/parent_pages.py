"""Parent-page aware retriever wrappers."""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from typing import Iterable, Sequence

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever


class ParentPageRetriever(BaseRetriever):
    """Wrap a retriever to promote chunk hits to their parent pages."""

    base_retriever: BaseRetriever
    parent_content_field: str = "parent_page_content"

    def __init__(
        self,
        *,
        base_retriever: BaseRetriever,
        parent_content_field: str = "parent_page_content",
    ) -> None:
        super().__init__(
            base_retriever=base_retriever,
            parent_content_field=parent_content_field,
        )

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun | None = None,
    ) -> Sequence[Document]:
        # Use invoke() for newer langchain versions, fallback to get_relevant_documents()
        if hasattr(self.base_retriever, "invoke"):
            documents = self.base_retriever.invoke(query)
        else:
            documents = self.base_retriever.get_relevant_documents(query)
        return self._collapse_to_parents(documents)

    async def _aget_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun | None = None,
    ) -> Sequence[Document]:
        # Try ainvoke first (newer API), then aget_relevant_documents, then fall back to sync
        if hasattr(self.base_retriever, "ainvoke"):
            documents = await self.base_retriever.ainvoke(query)
        elif hasattr(self.base_retriever, "aget_relevant_documents"):
            documents = await self.base_retriever.aget_relevant_documents(query)  # type: ignore[call-arg]
        elif hasattr(self.base_retriever, "invoke"):
            documents = await asyncio.to_thread(self.base_retriever.invoke, query)
        else:
            documents = await asyncio.to_thread(
                self.base_retriever.get_relevant_documents,
                query,
            )
        return self._collapse_to_parents(documents)

    def _collapse_to_parents(
        self,
        documents: Iterable[Document],
    ) -> Sequence[Document]:
        grouped: "OrderedDict[str, Document]" = OrderedDict()

        for doc in documents:
            metadata = dict(getattr(doc, "metadata", {}) or {})
            parent_id = metadata.get("parent_document_id") or self._build_parent_id(metadata)
            parent_content = metadata.get(self.parent_content_field)

            if parent_id is None or parent_content is None:
                grouped.setdefault(parent_id or f"chunk-{len(grouped)}", doc)
                continue

            if parent_id in grouped:
                continue

            parent_metadata = dict(metadata)
            parent_metadata.pop(self.parent_content_field, None)
            parent_metadata.setdefault("parent_page_number", metadata.get("page"))

            grouped[parent_id] = Document(
                page_content=str(parent_content),
                metadata=parent_metadata,
            )

        return list(grouped.values())

    @staticmethod
    def _build_parent_id(metadata: dict) -> str | None:
        source = metadata.get("source")
        if source is None:
            return None
        page_number = metadata.get("page") or metadata.get("parent_page_number")
        if page_number is None:
            return str(source)
        return f"{source}::page={page_number}"


__all__ = ["ParentPageRetriever"]
