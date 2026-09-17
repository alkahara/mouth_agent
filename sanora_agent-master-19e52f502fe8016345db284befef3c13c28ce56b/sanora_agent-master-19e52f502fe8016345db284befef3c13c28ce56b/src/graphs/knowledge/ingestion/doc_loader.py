"""DOC/DOCX document loading utilities."""

from __future__ import annotations

from pathlib import Path
from typing import List

from langchain_community.document_loaders import Docx2txtLoader
from langchain_core.documents import Document


SUPPORTED_DOC_SUFFIXES = {".doc", ".docx"}


def is_doc_file(path: Path) -> bool:
    """Return True if ``path`` looks like a Word document."""
    return path.suffix.lower() in SUPPORTED_DOC_SUFFIXES


def load_doc_documents(path: Path) -> List[Document]:
    """Load DOC/DOCX files via ``Docx2txtLoader``."""
    loader = Docx2txtLoader(str(path))
    return loader.load()


__all__ = ["SUPPORTED_DOC_SUFFIXES", "is_doc_file", "load_doc_documents"]
