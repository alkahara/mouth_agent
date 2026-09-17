"""Shared text splitting helpers for knowledge ingestion."""

from __future__ import annotations

from typing import Sequence

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document


def split_documents(
    documents: Sequence[Document],
    *,
    chunk_size: int,
    chunk_overlap: int,
) -> list[Document]:
    """Split documents into overlapping chunks for vectorization."""
    # 使用字符长度计算，避免 tiktoken 网络依赖
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
    )
    return splitter.split_documents(documents)


__all__ = ["split_documents"]
