"""Filesystem-based document ingestion helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

from langchain_core.documents import Document

from .doc_loader import is_doc_file, load_doc_documents


from .pdf_loader import load_pdf_documents
from ..preprocessing.labeling import load_label_mapping, merge_labels


ALLOWED_SUFFIXES = {".pdf", ".doc", ".docx"}


def iter_document_files(root: Path) -> Iterable[Path]:
    """Yield allowed document files from ``root`` recursively."""
    for file_path in sorted(root.rglob("*")):
        if file_path.is_file() and file_path.suffix.lower() in ALLOWED_SUFFIXES:
            yield file_path


def load_documents_from_directory(
    directory: Path,



) -> List[Document]:
    """Load documents from a knowledge base directory and apply labels."""
    documents: List[Document] = []
    label_mapping = load_label_mapping(directory)
    print(f"开始加载本地知识库：{directory}")



    for file_path in iter_document_files(directory):
        try:
            suffix = file_path.suffix.lower()
            if suffix == ".pdf":
                loaded_docs = load_pdf_documents(file_path)
            elif is_doc_file(file_path):
                loaded_docs = load_doc_documents(file_path)
            else:
                # Legacy fallback for additional text formats.
                text_content = file_path.read_text(encoding="utf-8")
                loaded_docs = [Document(page_content=text_content, metadata={"source": str(file_path)})]

            for doc in loaded_docs:
                metadata = dict(doc.metadata or {})
                metadata.setdefault("source", str(file_path))

                page_number = metadata.get("page")
                if page_number is not None:
                    metadata.setdefault("parent_page_number", page_number)

                parent_id_parts = [metadata["source"]]
                if page_number is not None:
                    parent_id_parts.append(f"page={page_number}")
                metadata.setdefault("parent_document_id", "::".join(parent_id_parts))

                metadata.setdefault("parent_page_content", doc.page_content)

                labels = label_mapping.get(file_path.name)
                if labels:
                    metadata["labels"] = merge_labels(metadata.get("labels"), list(labels))

                doc.metadata = metadata

            documents.extend(loaded_docs)

        except Exception as exc:  # noqa: BLE001
            print(f"跳过无法加载的文件 {file_path.name}: {exc}")

    print(f"知识库加载完成，得到 {len(documents)} 条文档片段")
    return documents


__all__ = ["ALLOWED_SUFFIXES", "iter_document_files", "load_documents_from_directory"]
