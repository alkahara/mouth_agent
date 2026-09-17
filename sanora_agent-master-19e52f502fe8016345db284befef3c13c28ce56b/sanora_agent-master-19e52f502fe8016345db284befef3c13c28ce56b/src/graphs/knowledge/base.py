"""Knowledge pack abstractions used by the agentic knowledge graph."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Sequence, Type

from langchain_core.embeddings import Embeddings
from .pipelines.prompts import DEFAULT_SYSTEM_PROMPT, DEFAULT_USER_PROMPT
from .pipelines.retriever_setup import (
    RetrieverResources,
    RetrieverSetup,
    build_retriever_resources,
)
from .pipelines.agentic_graph import build_agentic_state_graph, GraderRewriteRuntimeConfig
from .stores.vector_store import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_EMBEDDING_MODEL,
    create_embeddings,
)
from .rerank import RerankConfig


@dataclass(slots=True)
class PreprocessConfig:
    """Pre-ingestion configuration for remote sources and markdown extraction."""


    remote_urls: Sequence[str] = field(default_factory=tuple)


@dataclass(slots=True)
class ChunkingConfig:
    """Chunking parameters for all documents."""

    size: int = DEFAULT_CHUNK_SIZE
    overlap: int = DEFAULT_CHUNK_OVERLAP


@dataclass(slots=True)
class HybridRetrievalConfig:
    """Feature switches for hybrid retrieval."""

    enable_bm25: bool = False
    enable_parent_pages: bool = False


@dataclass(slots=True)
class QAPairsConfig:
    """Configuration for QA pairs retrieval."""

    enabled: bool = True
    prompt: str | None = None


@dataclass(slots=True)
class RetrievalConfig:
    """Tool metadata and search parameters."""

    tool_name: str
    tool_description: str
    search_kwargs: Dict[str, Any] | None = None
    hybrid: HybridRetrievalConfig = field(default_factory=HybridRetrievalConfig)
    qa_pairs: QAPairsConfig = field(default_factory=QAPairsConfig)
    llm_intent_query_retrieval: bool = True


@dataclass(slots=True)
class EmbeddingConfig:
    """Embedding settings for knowledge ingestion and retrieval."""

    model_key: str
    cache_dir: Path  # 缓存目录（必填）
    dataset_root: Path | None = None  # 数据集完整路径 = storage_root + dataset_path（可选）
    factory: Callable[[], Embeddings] | None = None
    storage_root: Path | None = None  # 存储根目录（用于 rebuild 时拼接相对路径）

    # 🔄 向后兼容属性（已废弃，请使用新命名）
    @property
    def knowledge_base_root(self) -> Path | None:
        """已废弃：请使用 dataset_root"""
        return self.dataset_root

    @property
    def uploads_root(self) -> Path | None:
        """已废弃：请使用 storage_root"""
        return self.storage_root


@dataclass(slots=True)
class GraderRewriteConfig:
    """Configuration for grader/rewrite pipeline."""

    enabled: bool = False
    grader_model_key: str | None = None
    rewrite_model_key: str | None = None
    grade_prompt: str | None = None
    rewrite_prompt: str | None = None

@dataclass(slots=True)
class PackMetadataConfig:
    """Human-readable metadata for a knowledge pack."""

    pack_id: str
    display_name: str
    description: str


@dataclass(slots=True)
class GenerateResponseConfig:
    """Generation LLM & prompt settings."""

    response_model_key: str
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    user_prompt: str = DEFAULT_USER_PROMPT


@dataclass(slots=True)
class KnowledgePack:
    """Declarative configuration for a domain-specific knowledge base."""

    metadata: PackMetadataConfig
    generate_response: GenerateResponseConfig
    retrieval: RetrievalConfig
    embedding: EmbeddingConfig
    preprocess: PreprocessConfig = field(default_factory=PreprocessConfig)
    chunking: ChunkingConfig = field(default_factory=ChunkingConfig)
    rerank_config: RerankConfig | None = None
    grader_rewrite: GraderRewriteConfig = field(
        default_factory=GraderRewriteConfig
    )

    @property
    def response_model_key(self) -> str:
        return self.generate_response.response_model_key

    def build_resources(self) -> RetrieverSetup:
        """Prepare the retriever builder inputs for this pack."""

        preprocess_cfg = self.preprocess
        chunk_cfg = self.chunking

        embedding_model = self.embedding.model_key or DEFAULT_EMBEDDING_MODEL
        embedding_factory = self.embedding.factory or (
            lambda: create_embeddings(embedding_model)
        )
        cache_dir = self.embedding.cache_dir
        dataset_root = self.embedding.dataset_root  # 🔄 使用新字段名

        retriever_kwargs = dict(self.retrieval.search_kwargs or {})
        enable_parent_pages = self.retrieval.hybrid.enable_parent_pages

        enable_bm25 = self.retrieval.hybrid.enable_bm25

        return RetrieverSetup(
            tool_name=self.retrieval.tool_name,
            tool_description=self.retrieval.tool_description,
            dataset_root=dataset_root,  # 🔄 使用新字段名
            cache_dir=cache_dir,
            pack_id=self.metadata.pack_id,
            remote_urls=tuple(preprocess_cfg.remote_urls),
            chunk_size=chunk_cfg.size,
            chunk_overlap=chunk_cfg.overlap,
            retriever_search_kwargs=retriever_kwargs or None,
            embedding_model=embedding_model,
            embedding_factory=embedding_factory,
            enable_bm25=enable_bm25,
            rerank_config=self.rerank_config,
            enable_parent_pages=enable_parent_pages,

            enable_qa_pairs=self.retrieval.qa_pairs.enabled,
            qa_pair_prompt_path=self.retrieval.qa_pairs.prompt,
        )

    def build_graph(
        self,
        llm_provider,
    ) -> tuple[Any, RetrieverResources]:
        """Create a compiled agentic RAG graph and its retriever resources."""

        generate_cfg = self.generate_response
        response_model = llm_provider.get_client(generate_cfg.response_model_key)
        if response_model is None:
            raise ValueError(
                f"Model '{generate_cfg.response_model_key}' is not available for pack '{self.metadata.pack_id}'"
            )

        rewrite_prompt = self.grader_rewrite.rewrite_prompt
        grade_prompt = self.grader_rewrite.grade_prompt

        if self.grader_rewrite.enabled and (not rewrite_prompt or not grade_prompt):
            raise ValueError(
                f"Grader rewrite enabled but prompts missing for pack '{self.metadata.pack_id}'"
            )

        system_prompt = generate_cfg.system_prompt
        user_prompt = generate_cfg.user_prompt or DEFAULT_USER_PROMPT
        if not system_prompt or not system_prompt.strip():
            raise ValueError(
                f"System prompt missing for pack '{self.metadata.pack_id}'. Please configure generate_response.system_prompt."
            )

        rewrite_model = None
        if self.grader_rewrite.rewrite_model_key:
            rewrite_model = llm_provider.get_client(
                self.grader_rewrite.rewrite_model_key
            )
            if rewrite_model is None:
                raise ValueError(
                    f"Model '{self.grader_rewrite.rewrite_model_key}' is not available for pack '{self.metadata.pack_id}'"
                )

        if self.grader_rewrite.enabled:
            grader_model_key = self.grader_rewrite.grader_model_key
            if not grader_model_key:
                raise ValueError(
                    f"Grader rewrite enabled but grader_model_key missing for pack '{self.metadata.pack_id}'"
                )
            grader_model = llm_provider.get_client(grader_model_key)
            if grader_model is None:
                raise ValueError(
                    f"Model '{grader_model_key}' is not available for pack '{self.metadata.pack_id}'"
                )
        else:
            grader_model = None

        retriever_setup = self.build_resources()
        resources = build_retriever_resources(retriever_setup)
        graph = build_agentic_state_graph(
            response_model=response_model,
            grader_model=grader_model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            retriever_tool=resources.retriever_tool,
            grader_rewrite=GraderRewriteRuntimeConfig(
                enabled=self.grader_rewrite.enabled,
                rewrite_model=rewrite_model,
                rewrite_prompt=rewrite_prompt,
                grade_prompt=grade_prompt,
            ),
            use_llm_intent_query_retrieval=self.retrieval.llm_intent_query_retrieval,
            base_retriever=resources.retriever,
        )

        return graph, resources


class KnowledgePackRegistry:
    """Global registry for knowledge packs."""

    _registry: Dict[str, Type[KnowledgePack]] = {}

    @classmethod
    def register(cls, pack_cls: Type[KnowledgePack]) -> Type[KnowledgePack]:
        pack_id = getattr(pack_cls, "PACK_ID", None) or getattr(pack_cls, "pack_id", None)
        if pack_id is None:
            raise ValueError(
                f"Knowledge pack class {pack_cls.__name__} must define PACK_ID or pack_id"
            )
        cls._registry[pack_id] = pack_cls
        return pack_cls

    @classmethod
    def list_packs(cls) -> Sequence[str]:
        from .config_loader import discover_configured_pack_ids

        registered = set(cls._registry.keys())
        configured = set(discover_configured_pack_ids())
        return tuple(sorted(registered | configured))

    @classmethod
    def create(cls, pack_id: str) -> KnowledgePack:
        pack_cls = cls._registry.get(pack_id)
        if pack_cls is None:
            from .config_loader import PackConfigError, build_pack_from_config

            try:
                return build_pack_from_config(pack_id)
            except PackConfigError as exc:
                raise ValueError(
                    f"Invalid configuration for knowledge pack '{pack_id}': {exc}"
                ) from exc

        return pack_cls()  # type: ignore[call-arg]


def register_pack(pack_cls: Type[KnowledgePack]) -> Type[KnowledgePack]:
    """Decorator helper to register a knowledge pack class."""

    return KnowledgePackRegistry.register(pack_cls)
