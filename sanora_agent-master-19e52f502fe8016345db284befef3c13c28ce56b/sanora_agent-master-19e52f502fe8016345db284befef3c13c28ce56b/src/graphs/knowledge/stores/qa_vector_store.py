"""问答对向量化和向量存储管理"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from .qa_store import QAPairStore, get_active_qa_pairs
from .vector_store import create_embeddings, DEFAULT_EMBEDDING_MODEL, load_faiss_local, save_faiss_local

_QA_FAISS_INDEX_NAME = "qa_faiss_index"


def build_qa_vectorstore(
    pack_id: str,
    cache_dir: Path,
    embedding_model: str = DEFAULT_EMBEDDING_MODEL,
    embedding_factory: Callable[[], Embeddings] | None = None,
) -> FAISS | None:
    """
    为问答对构建 FAISS 向量库

    Args:
        pack_id: 知识包 ID
        cache_dir: 缓存目录（vector_cache/）
        embedding_model: 嵌入模型名称
        embedding_factory: 自定义嵌入模型工厂函数

    Returns:
        FAISS 向量库，如果没有问答对则返回 None
    """
    qa_pairs_path = cache_dir / "qa_pairs.json"

    # 获取活跃的问答对
    active_qa_pairs = get_active_qa_pairs(qa_pairs_path)

    if not active_qa_pairs:
        print(f"知识包 {pack_id} 没有活跃的问答对")
        return None

    # 创建嵌入模型
    embeddings = (
        embedding_factory() if embedding_factory else create_embeddings(embedding_model)
    )

    # 将问答对转换为 Document 对象（用 question 作为 page_content）
    documents = []
    for qa in active_qa_pairs:
        doc = Document(
            page_content=qa.question,
            metadata={
                "qa_id": qa.qa_id,
                "pack_id": qa.pack_id,
                "answer": qa.answer,
                "session_id": qa.session_id,
                "quality_score": qa.quality_score,
                "usage_count": qa.usage_count,
                "created_at": qa.created_at,
                "type": "qa_pair",  # 标记为问答对
            },
        )
        documents.append(doc)

    print(f"为 {len(documents)} 个问答对创建向量索引")
    vectorstore = FAISS.from_documents(documents, embedding=embeddings)

    # 保存向量库
    save_faiss_local(vectorstore, cache_dir, _QA_FAISS_INDEX_NAME)
    print(f"问答对向量库已保存到 {cache_dir}")

    return vectorstore


def load_qa_vectorstore(
    cache_dir: Path,
    embedding_model: str = DEFAULT_EMBEDDING_MODEL,
    embedding_factory: Callable[[], Embeddings] | None = None,
) -> FAISS | None:
    """
    加载已保存的问答对向量库

    Args:
        cache_dir: 缓存目录
        embedding_model: 嵌入模型名称
        embedding_factory: 自定义嵌入模型工厂函数

    Returns:
        FAISS 向量库，如果不存在则返回 None
    """
    index_file = cache_dir / f"{_QA_FAISS_INDEX_NAME}.faiss"
    if not index_file.exists():
        return None

    embeddings = (
        embedding_factory() if embedding_factory else create_embeddings(embedding_model)
    )

    try:
        vectorstore = load_faiss_local(cache_dir, embeddings, _QA_FAISS_INDEX_NAME)
        print(f"已加载问答对向量库：{cache_dir}")
        return vectorstore
    except Exception as e:
        print(f"加载问答对向量库失败: {e}")
        return None


def add_qa_to_vectorstore(
    qa_id: str,
    question: str,
    answer: str,
    vectorstore: FAISS,
    pack_id: str,
    session_id: str,
    cache_dir: Path,
    metadata: dict | None = None,
) -> None:
    """
    增量添加单个问答对到现有向量库

    Args:
        qa_id: 问答对 ID
        question: 问题文本
        answer: 答案文本
        vectorstore: 现有的 FAISS 向量库
        pack_id: 知识包 ID
        session_id: 会话 ID
        cache_dir: 缓存目录
        metadata: 额外元数据
    """
    doc_metadata = {
        "qa_id": qa_id,
        "pack_id": pack_id,
        "answer": answer,
        "session_id": session_id,
        "quality_score": 0.0,
        "usage_count": 0,
        "type": "qa_pair",
    }

    if metadata:
        doc_metadata.update(metadata)

    # 创建 Document
    doc = Document(page_content=question, metadata=doc_metadata)

    # 添加到向量库
    vectorstore.add_documents([doc])

    # 保存更新后的向量库
    save_faiss_local(vectorstore, cache_dir, _QA_FAISS_INDEX_NAME)
    print(f"问答对 {qa_id} 已添加到向量库")


def rebuild_qa_vectorstore(
    pack_id: str,
    cache_dir: Path,
    embedding_model: str = DEFAULT_EMBEDDING_MODEL,
    embedding_factory: Callable[[], Embeddings] | None = None,
) -> FAISS | None:
    """
    强制重建问答对向量库

    Args:
        pack_id: 知识包 ID
        cache_dir: 缓存目录
        embedding_model: 嵌入模型名称
        embedding_factory: 自定义嵌入模型工厂函数

    Returns:
        新构建的 FAISS 向量库
    """
    # 删除旧索引（如果存在）
    index_file = cache_dir / f"{_QA_FAISS_INDEX_NAME}.faiss"
    pkl_file = cache_dir / f"{_QA_FAISS_INDEX_NAME}.pkl"

    if index_file.exists():
        index_file.unlink()
    if pkl_file.exists():
        pkl_file.unlink()

    # 重新构建
    return build_qa_vectorstore(
        pack_id=pack_id,
        cache_dir=cache_dir,
        embedding_model=embedding_model,
        embedding_factory=embedding_factory,
    )


class QAVectorStore:
    """问答对向量存储管理器（面向对象接口）"""

    def __init__(
        self,
        pack_id: str,
        cache_dir: Path,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
        embedding_factory: Callable[[], Embeddings] | None = None,
    ):
        """
        初始化向量存储管理器

        Args:
            pack_id: 知识包 ID
            cache_dir: 缓存目录
            embedding_model: 嵌入模型名称
            embedding_factory: 自定义嵌入模型工厂函数
        """
        self.pack_id = pack_id
        self.cache_dir = cache_dir
        self.embedding_model = embedding_model
        self.embedding_factory = embedding_factory
        self._vectorstore: Optional[FAISS] = None

    @property
    def vectorstore(self) -> FAISS | None:
        """懒加载向量库"""
        if self._vectorstore is None:
            self._vectorstore = load_qa_vectorstore(
                cache_dir=self.cache_dir,
                embedding_model=self.embedding_model,
                embedding_factory=self.embedding_factory,
            )
        return self._vectorstore

    def build(self) -> FAISS | None:
        """构建向量库"""
        self._vectorstore = build_qa_vectorstore(
            pack_id=self.pack_id,
            cache_dir=self.cache_dir,
            embedding_model=self.embedding_model,
            embedding_factory=self.embedding_factory,
        )
        return self._vectorstore

    def rebuild(self) -> FAISS | None:
        """重建向量库"""
        self._vectorstore = rebuild_qa_vectorstore(
            pack_id=self.pack_id,
            cache_dir=self.cache_dir,
            embedding_model=self.embedding_model,
            embedding_factory=self.embedding_factory,
        )
        return self._vectorstore

    def add_qa(
        self, qa_id: str, question: str, answer: str, session_id: str, metadata: dict | None = None
    ) -> None:
        """添加单个问答对"""
        if self.vectorstore is None:
            # 如果向量库不存在，先构建
            self.build()

        if self.vectorstore is not None:
            add_qa_to_vectorstore(
                qa_id=qa_id,
                question=question,
                answer=answer,
                vectorstore=self.vectorstore,
                pack_id=self.pack_id,
                session_id=session_id,
                cache_dir=self.cache_dir,
                metadata=metadata,
            )


__all__ = [
    "QAVectorStore",
    "build_qa_vectorstore",
    "load_qa_vectorstore",
    "add_qa_to_vectorstore",
    "rebuild_qa_vectorstore",
]
