"""Vector-store construction and caching utilities."""

from __future__ import annotations

import json
import shutil
from tempfile import TemporaryDirectory
from pathlib import Path
from typing import Any, Callable, Sequence

from langchain_community.embeddings import DashScopeEmbeddings
from langchain_community.retrievers import BM25Retriever
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from ..ingestion.filesystem import load_documents_from_directory
from ..ingestion.web_loader import load_remote_documents
from ..preprocessing.text_splitter import split_documents
from ..retrieval import HybridVectorRetriever, DEFAULT_RETRIEVAL_TOP_K

DEFAULT_EMBEDDING_MODEL = "text-embedding-v4"
DEFAULT_CHUNK_SIZE = 800
DEFAULT_CHUNK_OVERLAP = 80
_FAISS_INDEX_NAME = "faiss_index"
_CONFIG_FILENAME = "config.json"


def create_embeddings(model: str = DEFAULT_EMBEDDING_MODEL) -> Embeddings:
    """Construct DashScope embedding instances."""
    try:
        return DashScopeEmbeddings(model=model)
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "DashScope embeddings 未安装。请安装 langchain_community[dashscope] 或在 pack 中自定义 embedding_factory"
        ) from exc


def prepare_combined_vectorstore(
    urls: Sequence[str],
    *,
    user_agent: str | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    dataset_root: Path | None,  # 🔄 新命名：数据集完整路径
    cache_dir: Path,
    embedding_model: str = DEFAULT_EMBEDDING_MODEL,
    embedding_factory: Callable[[], Embeddings] | None = None,
    enable_bm25: bool = True,

    pack_id: str = "unknown",
    allow_empty: bool = True,
) -> "HybridVectorRetriever | FAISS | None":
    """Build (or load) a hybrid vector store that mixes semantic and keyword search.

    Args:
        allow_empty: 如果为 True，在没有文档时返回 None 而不是抛出异常（方案B：支持空知识库启动）
    """
    embeddings = embedding_factory() if embedding_factory else create_embeddings(embedding_model)

    vectorstore = _load_or_build_vectorstore(
        dataset_root=dataset_root,  # 🔄 使用新字段名
        cache_dir=cache_dir,
        embeddings=embeddings,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        embedding_model=embedding_model,

        pack_id=pack_id,
    )

    remote_docs = load_remote_documents(urls, user_agent=user_agent) if urls else []
    if remote_docs:
        remote_splits = split_documents(
            remote_docs, chunk_size=chunk_size, chunk_overlap=chunk_overlap
        )
        if remote_splits:
            remote_vs = FAISS.from_documents(remote_splits, embedding=embeddings)
            if vectorstore is None:
                vectorstore = remote_vs
            else:
                vectorstore.merge_from(remote_vs)

    if vectorstore is None:
        if allow_empty:
            print(f"⚠️  知识库为空（目录: {dataset_root}），服务可正常启动，等待文档上传后调用 rebuild")
            return None
        raise ValueError("没有可用文档来构建向量库。")

    if not enable_bm25:
        return vectorstore

    keyword_docs = _extract_documents_from_vectorstore(vectorstore)
    if not keyword_docs:
        if allow_empty:
            return vectorstore
        raise ValueError("向量库未包含任何文档，无法构建混合检索。")

    keyword_retriever = BM25Retriever.from_documents(keyword_docs)
    return HybridVectorRetriever(semantic_store=vectorstore, keyword_retriever=keyword_retriever)


def _load_or_build_vectorstore(
    *,
    dataset_root: Path | None,  # 🔄 新命名：数据集完整路径
    cache_dir: Path,
    embeddings: Embeddings,
    chunk_size: int,
    chunk_overlap: int,
    embedding_model: str,

    pack_id: str = "unknown",
) -> FAISS | None:
    # 🆕 支持空知识库：dataset_root 可能为 None
    if dataset_root is None or not dataset_root.exists():
        return None

    cache_dir.mkdir(parents=True, exist_ok=True)
    config = _build_cache_config(
        dataset_root,  # 🔄 使用新字段名
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        embedding_model=embedding_model,
    )
    config_path = cache_dir / _CONFIG_FILENAME
    index_files_exist = _faiss_index_exists(cache_dir)

    if index_files_exist and config_path.exists():
        saved_config = json.loads(config_path.read_text(encoding="utf-8"))
        if saved_config == config:
            print(f"使用缓存向量库：{cache_dir}")
            return load_faiss_local(cache_dir, embeddings, _FAISS_INDEX_NAME)
        print("检测到知识库文档变化，重新构建向量库")

    documents = load_documents_from_directory(
        dataset_root,  # 🔄 使用新字段名


    )
    if not documents:
        print(f"知识库目录 {dataset_root} 未加载到任何文档")
        return None

    from ..preprocessing.enhanced_splitter import split_documents_with_positions
    splits, document_chunks_list = split_documents_with_positions(
        documents,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        pack_id=pack_id,
    )

    if not splits:
        print("文档切分结果为空，无法构建向量库")
        return None

    print(f"知识库切分后共有 {len(splits)} 条片段，开始创建 FAISS 向量库")
    vectorstore = FAISS.from_documents(splits, embedding=embeddings)
    save_faiss_local(vectorstore, cache_dir, _FAISS_INDEX_NAME)

    # 保存切片元数据
    if document_chunks_list:
        from .metadata_store import save_chunks_metadata

        metadata_path = cache_dir / "chunks_metadata.json"
        save_chunks_metadata(
            pack_id=pack_id,
            document_chunks_list=document_chunks_list,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            output_path=metadata_path,
        )
        print(f"切片元数据已保存到 {metadata_path}")

    config_with_stats = dict(config)
    config_with_stats["chunk_count"] = len(splits)
    config_path.write_text(json.dumps(config_with_stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"知识库向量库已保存到 {cache_dir}")
    return vectorstore


def _build_cache_config(
    source_dir: Path,
    *,
    chunk_size: int,
    chunk_overlap: int,
    embedding_model: str,
) -> dict:
    files = []
    for file_path in sorted(source_dir.rglob("*")):
        if file_path.is_file():
            files.append(
                {
                    "path": file_path.relative_to(source_dir).as_posix(),
                    "mtime_ns": file_path.stat().st_mtime_ns,
                    "size": file_path.stat().st_size,
                }
            )
    return {
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
        "embedding_model": embedding_model,
        "files": files,
    }


def _faiss_index_exists(cache_dir: Path) -> bool:
    index_file = cache_dir / f"{_FAISS_INDEX_NAME}.faiss"
    store_file = cache_dir / f"{_FAISS_INDEX_NAME}.pkl"
    return index_file.exists() and store_file.exists()


def load_faiss_local(cache_dir: Path, embeddings: Embeddings, index_name: str) -> FAISS:
    """Load FAISS through an ASCII path on Windows installations with Unicode paths."""
    if str(cache_dir).isascii():
        return FAISS.load_local(
            cache_dir, embeddings, index_name=index_name, allow_dangerous_deserialization=True
        )

    with TemporaryDirectory(prefix="faiss-cache-") as temp_dir:
        temp_path = Path(temp_dir)
        for suffix in (".faiss", ".pkl"):
            shutil.copy2(cache_dir / f"{index_name}{suffix}", temp_path / f"{index_name}{suffix}")
        return FAISS.load_local(
            temp_path, embeddings, index_name=index_name, allow_dangerous_deserialization=True
        )


def save_faiss_local(vectorstore: FAISS, cache_dir: Path, index_name: str) -> None:
    """Save FAISS through an ASCII path when its native writer cannot open Unicode paths."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    if str(cache_dir).isascii():
        vectorstore.save_local(cache_dir, index_name=index_name)
        return

    with TemporaryDirectory(prefix="faiss-cache-") as temp_dir:
        temp_path = Path(temp_dir)
        vectorstore.save_local(temp_path, index_name=index_name)
        for suffix in (".faiss", ".pkl"):
            shutil.copy2(temp_path / f"{index_name}{suffix}", cache_dir / f"{index_name}{suffix}")


def _extract_documents_from_vectorstore(vectorstore: FAISS) -> list[Document]:
    docstore = getattr(vectorstore, "docstore", None)
    if docstore is None:
        return []

    documents: list[Document] = []
    storage = None
    if hasattr(docstore, "_dict"):
        storage = docstore._dict  # type: ignore[attr-defined]
    elif hasattr(docstore, "dict"):
        storage = docstore.dict  # type: ignore[attr-defined]

    if storage is not None:
        documents.extend(storage.values())
    return documents


def collect_vectorstore_documents(vectorstore: FAISS) -> list[Document]:
    """Return all documents stored within a FAISS vector store."""
    return _extract_documents_from_vectorstore(vectorstore)


__all__ = [
    "prepare_combined_vectorstore",
    "collect_vectorstore_documents",
    "create_embeddings",
    "DEFAULT_CHUNK_SIZE",
    "DEFAULT_CHUNK_OVERLAP",
    "DEFAULT_EMBEDDING_MODEL",
    "DEFAULT_RETRIEVAL_TOP_K",
]
