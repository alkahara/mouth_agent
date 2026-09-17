"""Ingestion helpers for knowledge packs."""

from .pdf_loader import load_pdf_documents
from .doc_loader import load_doc_documents, is_doc_file, SUPPORTED_DOC_SUFFIXES
from .web_loader import load_remote_documents
from .filesystem import (
    ALLOWED_SUFFIXES,
    iter_document_files,
    load_documents_from_directory,
)

__all__ = [
    "load_pdf_documents",
    "load_doc_documents",
    "is_doc_file",
    "SUPPORTED_DOC_SUFFIXES",
    "load_remote_documents",
    "ALLOWED_SUFFIXES",
    "iter_document_files",
    "load_documents_from_directory",
]
