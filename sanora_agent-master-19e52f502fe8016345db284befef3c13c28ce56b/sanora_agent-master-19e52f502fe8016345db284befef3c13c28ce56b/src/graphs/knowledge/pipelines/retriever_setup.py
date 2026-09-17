"""Retriever setup and resource construction."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Sequence

from langchain_core.tools import create_retriever_tool
from langchain_core.embeddings import Embeddings
from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document
from langchain_core.callbacks import CallbackManagerForRetrieverRun

from ..stores.vector_store import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_EMBEDDING_MODEL,
    prepare_combined_vectorstore,
)
from ..stores.qa_vector_store import load_qa_vectorstore
from ..retrieval.retrieval import DEFAULT_RETRIEVAL_TOP_K
from ..rerank import RerankConfig, RerankRetriever, build_reranker
from ..retrieval.parent_pages import ParentPageRetriever
from ..retrieval.hybrid_doc_qa_retriever import create_hybrid_doc_qa_retriever


logger = logging.getLogger(__name__)


class EmptyRetriever(BaseRetriever):
    """空的检索器，用于知识库为空时（方案B：支持空知识库启动）"""

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> List[Document]:
        """返回空列表，表示没有相关文档"""
        return []


@dataclass(slots=True)
class RetrieverSetup:
    """Configuration required to prepare retriever resources."""

    tool_name: str
    tool_description: str
    dataset_root: Path | None  # 🔄 新命名：数据集完整路径
    cache_dir: Path
    pack_id: str = "unknown"
    remote_urls: Sequence[str] = ()
    chunk_size: int = DEFAULT_CHUNK_SIZE
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP
    retriever_search_kwargs: Dict[str, Any] | None = None
    embedding_model: str = DEFAULT_EMBEDDING_MODEL
    embedding_factory: Callable[[], Embeddings] | None = None
    enable_bm25: bool = True
    rerank_config: RerankConfig | None = None
    enable_parent_pages: bool = False

    enable_qa_pairs: bool = True
    qa_pair_prompt_path: str | None = None


@dataclass(slots=True)
class RetrieverResources:
    """Container for retriever related objects."""

    retriever_tool: Any
    retriever: Any
    vectorstore: Any
    reranker: Any | None = None
    qa_vectorstore: Any | None = None


def build_retriever_resources(setup: RetrieverSetup) -> RetrieverResources:
    """Build a hybrid retriever tool backed by the configured knowledge base."""

    vectorstore = prepare_combined_vectorstore(
        setup.remote_urls,
        chunk_size=setup.chunk_size,
        chunk_overlap=setup.chunk_overlap,
        dataset_root=setup.dataset_root,  # 🔄 使用新字段名
        cache_dir=setup.cache_dir,
        embedding_model=setup.embedding_model,
        embedding_factory=setup.embedding_factory,
        enable_bm25=setup.enable_bm25,

        pack_id=setup.pack_id,
        allow_empty=True,  # 方案B：支持空知识库启动
    )

    # 方案B：如果文档向量库为空，尝试只用问答对向量库
    if vectorstore is None:
        logger.warning(f"文档知识库为空，尝试加载问答对向量库...")
        
        # 🔧 修复：即使文档为空，也要尝试加载问答对向量库
        qa_vectorstore = None
        retriever = EmptyRetriever()  # 默认使用空检索器
        
        if setup.enable_qa_pairs:
            try:
                qa_vectorstore = load_qa_vectorstore(
                    cache_dir=setup.cache_dir,
                    embedding_model=setup.embedding_model,
                    embedding_factory=setup.embedding_factory,
                )
                if qa_vectorstore is not None:
                    logger.info("✅ 已加载问答对向量库（文档知识库为空）")
                    
                    # 加载问答对模板
                    qa_pair_template = None
                    if setup.qa_pair_prompt_path:
                        template_path = setup.cache_dir.parent / setup.qa_pair_prompt_path
                    else:
                        template_path = setup.cache_dir.parent / "prompts" / "qa_pair.md"
                    
                    if template_path.exists():
                        try:
                            with open(template_path, 'r', encoding='utf-8') as f:
                                qa_pair_template = f.read().strip()
                            logger.info(f"已加载问答对模板: {template_path}")
                        except Exception as e:
                            logger.warning(f"加载问答对模板失败: {e}")
                    
                    # 使用纯问答对检索器（无文档混合）
                    retriever = create_hybrid_doc_qa_retriever(
                        doc_retriever=EmptyRetriever(),  # 空文档检索器
                        qa_vectorstore=qa_vectorstore,
                        doc_k=0,  # 不从文档检索
                        qa_k=10,  # 只从问答对检索
                        qa_score_boost=1.0,
                        qa_pair_template=qa_pair_template,
                    )
                else:
                    logger.warning("问答对向量库也为空，使用空检索器")
            except Exception as exc:
                logger.warning("加载问答对向量库失败: %s", exc)
        else:
            logger.warning("知识库为空且问答对功能已禁用，使用空检索器")
        
        retriever_tool = create_retriever_tool(
            retriever,
            setup.tool_name,
            setup.tool_description,
        )
        return RetrieverResources(
            retriever_tool=retriever_tool,
            retriever=retriever,
            vectorstore=None,
            reranker=None,
            qa_vectorstore=qa_vectorstore,
        )

    search_kwargs = dict(setup.retriever_search_kwargs or {})
    reranker = None
    rerank_config = setup.rerank_config

    if rerank_config:
        try:
            reranker = build_reranker(rerank_config)
        except Exception as exc:  # pragma: no cover - initialization failures
            logger.warning(
                "Failed to initialize reranker for tool '%s': %s",
                setup.tool_name,
                exc,
            )
            reranker = None
        else:
            if reranker is not None:
                base_k = search_kwargs.get("k", DEFAULT_RETRIEVAL_TOP_K)
                candidate_k = rerank_config.candidate_k or base_k
                if rerank_config.top_k:
                    candidate_k = max(candidate_k, rerank_config.top_k)
                search_kwargs["k"] = candidate_k

    base_retriever = vectorstore.as_retriever(search_kwargs=search_kwargs)
    retriever = base_retriever

    if reranker is not None:
        retriever = RerankRetriever(
            base_retriever=retriever,
            reranker=reranker,
            top_k=rerank_config.top_k if rerank_config else None,
        )

    if setup.enable_parent_pages:
        retriever = ParentPageRetriever(base_retriever=retriever)

    # 加载问答对向量库（如果配置启用）
    qa_vectorstore = None
    if setup.enable_qa_pairs:
        try:
            qa_vectorstore = load_qa_vectorstore(
                cache_dir=setup.cache_dir,
                embedding_model=setup.embedding_model,
                embedding_factory=setup.embedding_factory,
            )
            if qa_vectorstore is not None:
                logger.info("已加载问答对向量库，将使用混合检索")

                # 尝试加载问答对模板
                qa_pair_template = None
                if setup.qa_pair_prompt_path:
                    # 使用配置的路径（相对于 pack 目录）
                    template_path = setup.cache_dir.parent / setup.qa_pair_prompt_path
                else:
                    # 使用默认路径
                    template_path = setup.cache_dir.parent / "prompts" / "qa_pair.md"

                if template_path.exists():
                    try:
                        with open(template_path, 'r', encoding='utf-8') as f:
                            qa_pair_template = f.read().strip()
                        logger.info(f"已加载问答对模板: {template_path}")
                    except Exception as e:
                        logger.warning(f"加载问答对模板失败: {e}，将使用默认格式")

                # 使用混合检索器
                retriever = create_hybrid_doc_qa_retriever(
                    doc_retriever=retriever,
                    qa_vectorstore=qa_vectorstore,
                    doc_k=7,
                    qa_k=3,
                    qa_score_boost=1.2,
                    qa_pair_template=qa_pair_template,
                )
        except Exception as exc:
            logger.warning("加载问答对向量库失败: %s", exc)
            qa_vectorstore = None
    else:
        logger.info("问答对功能已禁用（enable_qa_pairs=false）")

    retriever_tool = create_retriever_tool(
        retriever,
        setup.tool_name,
        setup.tool_description,
    )

    return RetrieverResources(
        retriever_tool=retriever_tool,
        retriever=retriever,
        vectorstore=vectorstore,
        reranker=reranker,
        qa_vectorstore=qa_vectorstore,
    )


__all__ = [
    "RetrieverSetup",
    "RetrieverResources",
    "build_retriever_resources",
]
