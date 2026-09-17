"""Remote document loaders (HTTP URLs)."""

from __future__ import annotations

from typing import List, Sequence

from langchain_community.document_loaders import WebBaseLoader
from langchain_core.documents import Document


def load_remote_documents(urls: Sequence[str], *, user_agent: str | None = None) -> List[Document]:
    """Fetch remote documents with optional User-Agent header."""
    requests_kwargs = {"headers": {"User-Agent": user_agent}} if user_agent else None
    documents: List[Document] = []
    if urls:
        print(f"开始抓取远程文档，共 {len(urls)} 个 URL")
    for url in urls:
        loader = WebBaseLoader(url, requests_kwargs=requests_kwargs) if requests_kwargs else WebBaseLoader(url)
        documents.extend(loader.load())
    if urls:
        print(f"远程文档抓取完成，得到 {len(documents)} 条文档片段")
    return documents


__all__ = ["load_remote_documents"]
