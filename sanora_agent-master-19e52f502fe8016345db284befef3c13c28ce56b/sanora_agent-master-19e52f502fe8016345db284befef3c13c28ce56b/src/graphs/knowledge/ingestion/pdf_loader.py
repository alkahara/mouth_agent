"""PDF document loading utilities for knowledge ingestion."""

from __future__ import annotations

from pathlib import Path
from typing import List

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document


def load_pdf_documents(path: Path) -> List[Document]:
    """Load a PDF file into LangChain ``Document`` chunks."""
    loader = PyPDFLoader(str(path))
    return loader.load()


__all__ = ["load_pdf_documents"]
