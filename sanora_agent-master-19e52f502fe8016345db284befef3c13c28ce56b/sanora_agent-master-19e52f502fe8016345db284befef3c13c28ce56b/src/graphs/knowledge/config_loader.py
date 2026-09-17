"""Helpers for loading knowledge pack definitions from YAML configuration."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping, MutableMapping, Sequence
from pathlib import Path
from typing import Any, Dict

import yaml

from .base import (
    KnowledgePack,
    PreprocessConfig,
    ChunkingConfig,
    RetrievalConfig,
    HybridRetrievalConfig,
    EmbeddingConfig,
    PackMetadataConfig,
    GenerateResponseConfig,
)
from .base import GraderRewriteConfig
from .pipelines.prompts import DEFAULT_SYSTEM_PROMPT, DEFAULT_USER_PROMPT
from .rerank import RerankConfig, RerankProvider
from .stores.vector_store import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_EMBEDDING_MODEL,
)

try:
    from langchain_openai import OpenAIEmbeddings
except ImportError:  # pragma: no cover - optional dependency for specific packs
    OpenAIEmbeddings = None  # type: ignore[assignment]

PACK_CONFIG_FILENAME = "pack.yaml"
PACKS_DIR = Path(__file__).resolve().parent / "packs"
_PROMPT_CACHE: Dict[tuple[str, str], str] = {}

# 环境变量占位符正则: ${VAR_NAME}
_ENV_VAR_PATTERN = re.compile(r'\$\{([A-Za-z_][A-Za-z0-9_]*)\}')


def _expand_env_vars(value: str) -> str:
    """
    将字符串中的 ${ENV_VAR} 替换为对应的环境变量值。
    
    示例：
        "${SHELD_EMBEDDING_STORAGE_ROOT}/data" -> "/var/sheld/uploads/data"
    
    如果环境变量未设置，保留原始占位符并记录警告。
    """
    def replace_match(match: re.Match) -> str:
        var_name = match.group(1)
        env_value = os.environ.get(var_name)
        if env_value is None:
            import logging
            logging.getLogger(__name__).warning(
                f"环境变量 '{var_name}' 未设置，请在 .env 或系统环境中配置"
            )
            return match.group(0)  # 保留原始占位符
        return env_value
    
    return _ENV_VAR_PATTERN.sub(replace_match, value)


class PackConfigError(RuntimeError):
    """Raised when a pack configuration file is invalid."""


def discover_configured_pack_ids() -> Sequence[str]:
    """Return all pack ids that expose a YAML configuration file."""

    if not PACKS_DIR.exists():
        return ()

    pack_ids: list[str] = []
    for entry in PACKS_DIR.iterdir():
        if not entry.is_dir():
            continue
        if (entry / PACK_CONFIG_FILENAME).is_file():
            pack_ids.append(entry.name)
    return tuple(sorted(pack_ids))


def load_pack_document(pack_id: str) -> MutableMapping[str, Any]:
    """Load the raw YAML document for the given pack id."""

    config_path = PACKS_DIR / pack_id / PACK_CONFIG_FILENAME
    if not config_path.is_file():
        raise PackConfigError(f"Pack '{pack_id}' missing configuration file: {config_path}")

    with config_path.open("r", encoding="utf-8") as handle:
        try:
            payload = yaml.safe_load(handle)
        except yaml.YAMLError as exc:  # pragma: no cover - PyYAML error formatting
            raise PackConfigError(f"Failed to parse pack '{pack_id}' config: {exc}") from exc

    if not isinstance(payload, MutableMapping):
        raise PackConfigError(
            f"Pack '{pack_id}' configuration must be a mapping, received: {type(payload)!r}"
        )

    return payload


def _resolve_prompt_text(
    pack_id: str, field_name: str, raw_value: str | None, base_dir: Path, default_text: str
) -> str:
    """Return prompt text, reading from disk when a markdown path is provided."""

    if not raw_value:
        return default_text

    candidate_path = Path(raw_value)
    if not candidate_path.is_absolute():
        candidate_path = (base_dir / raw_value).resolve(strict=False)

    if candidate_path.is_file():
        cache_key = (pack_id, str(candidate_path))
        if cache_key in _PROMPT_CACHE:
            return _PROMPT_CACHE[cache_key]

        try:
            text = candidate_path.read_text(encoding="utf-8")
        except OSError as exc:  # pragma: no cover - filesystem error
            raise PackConfigError(
                f"Pack '{pack_id}' failed to read prompt file '{raw_value}' for field '{field_name}': {exc}"
            ) from exc

        _PROMPT_CACHE[cache_key] = text
        return text

    return raw_value


def _resolve_preprocess(payload: Mapping[str, Any]) -> PreprocessConfig:
    section = payload.get("preprocess")
    if section is None:
        section = {}
    if not isinstance(section, Mapping):
        raise PackConfigError("pack must define a 'preprocess' mapping")


    remote_urls = section.get("remote_urls") or []
    if not isinstance(remote_urls, Sequence) or isinstance(remote_urls, (str, bytes)):
        raise PackConfigError("preprocess.remote_urls must be a sequence of strings")

    normalized: list[str] = []
    for url in remote_urls:
        if not isinstance(url, str):
            raise PackConfigError("preprocess.remote_urls entries must be strings")
        normalized.append(url)

    return PreprocessConfig(

        remote_urls=tuple(normalized),
    )


def _resolve_generate_response_config(
    pack_id: str, payload: Mapping[str, Any], base_dir: Path
) -> GenerateResponseConfig:
    """Load response model key and prompts from the generate_response block."""

    section = payload.get("generate_response")
    if not isinstance(section, Mapping):
        raise PackConfigError(
            f"Pack '{pack_id}' must define a 'generate_response' mapping"
        )

    response_model = section.get("response_model_key") or section.get("response_model")
    if not isinstance(response_model, str) or not response_model.strip():
        raise PackConfigError(
            f"Pack '{pack_id}' generate_response.response_model_key must be a non-empty string"
        )

    system_prompt_value = section.get("system_prompt")
    if system_prompt_value is None or not isinstance(system_prompt_value, str):
        raise PackConfigError(
            f"Pack '{pack_id}' generate_response.system_prompt must be a string and cannot be omitted"
        )
    if not system_prompt_value.strip():
        raise PackConfigError(
            f"Pack '{pack_id}' generate_response.system_prompt must not be empty"
        )

    user_prompt_value = section.get("user_prompt")
    if user_prompt_value is not None and not isinstance(user_prompt_value, str):
        raise PackConfigError(
            f"Pack '{pack_id}' generate_response.user_prompt must be a string when provided"
        )

    system_prompt = _resolve_prompt_text(
        pack_id,
        "generate_response.system_prompt",
        system_prompt_value,
        base_dir,
        system_prompt_value,
    )
    if not system_prompt.strip():
        raise PackConfigError(
            f"Pack '{pack_id}' generate_response.system_prompt resolved to empty content"
        )
    user_prompt = _resolve_prompt_text(
        pack_id,
        "generate_response.user_prompt",
        user_prompt_value,
        base_dir,
        DEFAULT_USER_PROMPT,
    )

    return GenerateResponseConfig(
        response_model_key=response_model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )


def _resolve_grader_rewrite_config(
    pack_id: str,
    payload: Mapping[str, Any],
    base_dir: Path,
    legacy_rewrite_prompt: str | None,
    legacy_grade_prompt: str | None,
) -> GraderRewriteConfig:
    section = payload.get("grader_rewrite")
    if section is None:
        return GraderRewriteConfig()
    if not isinstance(section, Mapping):
        raise PackConfigError("grader_rewrite section must be a mapping if provided")

    enabled = bool(section.get("enabled", False))

    def _resolve_optional_prompt(key: str) -> str | None:
        value = section.get(key)
        if value is None:
            return None
        if not isinstance(value, str):
            raise PackConfigError(
                f"Pack '{pack_id}' grader_rewrite.{key} must be a string when provided"
            )
        return _resolve_prompt_text(
            pack_id,
            f"grader_rewrite.{key}",
            value,
            base_dir,
            value,
        )
    grader_model = section.get("grader_model")
    if grader_model is not None and not isinstance(grader_model, str):
        raise PackConfigError(
            f"Pack '{pack_id}' grader_rewrite.grader_model must be a string when provided"
        )

    rewrite_model = section.get("rewrite_model")
    if rewrite_model is not None and not isinstance(rewrite_model, str):
        raise PackConfigError(
            f"Pack '{pack_id}' grader_rewrite.rewrite_model must be a string when provided"
        )

    rewrite_prompt = _resolve_optional_prompt("rewrite_prompt") or legacy_rewrite_prompt
    grade_prompt = _resolve_optional_prompt("grade_prompt") or legacy_grade_prompt
    if enabled and (not rewrite_prompt or not grade_prompt):
        raise PackConfigError(
            f"Pack '{pack_id}' grader_rewrite enabled but rewrite/grade prompts missing"
        )
    if enabled and not grader_model:
        raise PackConfigError(
            f"Pack '{pack_id}' grader_rewrite enabled but grader_model missing"
        )

    return GraderRewriteConfig(
        enabled=enabled,
        grader_model_key=grader_model,
        rewrite_model_key=rewrite_model,
        grade_prompt=grade_prompt,
        rewrite_prompt=rewrite_prompt,
    )


def _resolve_embedding_config(
    pack_id: str, payload: Mapping[str, Any], base_dir: Path
) -> EmbeddingConfig:
    section = payload.get("embedding")
    if section is None:
        section = {}
    if not isinstance(section, Mapping):
        raise PackConfigError("embedding section must be a mapping")

    model_key = section.get("model_key") or section.get("model") or DEFAULT_EMBEDDING_MODEL
    if not isinstance(model_key, str):
        raise PackConfigError(
            f"Pack '{pack_id}' embedding.model_key must be a string, received: {type(model_key)!r}"
        )

    path_section = section.get("path") or {}
    if not isinstance(path_section, Mapping):
        raise PackConfigError("embedding.path must be a mapping when provided")

    # 🔄 解析 storage_root（存储根目录，用于 rebuild 时拼接相对路径）
    # 支持新命名 storage_root，向后兼容旧命名 uploads_root
    # 🆕 支持环境变量语法: ${ENV_VAR}
    storage_root_value = path_section.get("storage_root") or path_section.get("uploads_root")
    storage_root = None
    if storage_root_value:
        if not isinstance(storage_root_value, str):
            raise PackConfigError("embedding.path.storage_root must be a string")
        # 应用环境变量替换
        expanded_value = _expand_env_vars(storage_root_value)
        storage_root = Path(expanded_value).resolve()

    # 🔄 解析 dataset_path（数据集路径）
    # 支持新命名 dataset_path，向后兼容旧命名 knowledge_base
    dataset_path_value = path_section.get("dataset_path") or path_section.get("knowledge_base", "knowledge_base")
    cache_path_value = path_section.get("cache", "vector_cache")

    # 🆕 允许 dataset_path 为 None（支持空知识库场景）
    if dataset_path_value is not None and not isinstance(dataset_path_value, str):
        raise PackConfigError("embedding.path.dataset_path must be a string or null")

    if not isinstance(cache_path_value, str):
        raise PackConfigError("embedding.path.cache must be a string")

    # 🆕 处理空知识库场景（dataset_path: null）
    dataset_root = None
    if dataset_path_value is not None:
        dataset_path = Path(dataset_path_value)

        # 如果指定了 storage_root，dataset_path 作为相对路径拼接
        if storage_root:
            if dataset_path.is_absolute():
                # 绝对路径直接使用
                dataset_root = dataset_path.resolve()
            else:
                # 相对路径与 storage_root 拼接
                dataset_root = (storage_root / dataset_path).resolve()
        else:
            # 兼容旧配置：没有 storage_root 时使用原有逻辑
            if not dataset_path.is_absolute():
                dataset_root = (base_dir / dataset_path).resolve()
            else:
                dataset_root = dataset_path.resolve()
    # else: dataset_root 保持为 None，支持空知识库启动

    cache_path = Path(cache_path_value)
    if not cache_path.is_absolute():
        cache_path = (base_dir / cache_path).resolve()
    else:
        cache_path = cache_path.resolve()

    provider = section.get("provider")
    factory = None
    if provider is not None:
        if not isinstance(provider, str):
            raise PackConfigError(
                f"Pack '{pack_id}' embedding.provider must be a string when provided"
            )
        if provider.lower() == "openai":
            if OpenAIEmbeddings is None:
                raise PackConfigError(
                    "OpenAI embeddings requested but langchain-openai is not installed"
                )

            def factory() -> Any:
                return OpenAIEmbeddings(model=model_key)

        else:
            # For unsupported providers, fall back to default factory-less behavior.
            factory = None

    return EmbeddingConfig(
        model_key=model_key,
        cache_dir=cache_path,
        dataset_root=dataset_root,  # 🔄 新命名
        factory=factory,
        storage_root=storage_root,  # 🔄 新命名
    )


def _resolve_retrieval(pack_id: str, payload: Mapping[str, Any]) -> RetrievalConfig:
    section = payload.get("retrieval")
    if section is None:
        legacy = payload.get("retriever")
        if legacy is None:
            raise PackConfigError(f"Pack '{pack_id}' must define a 'retrieval' mapping")
        return _resolve_legacy_retriever(pack_id, legacy)

    if not isinstance(section, Mapping):
        raise PackConfigError(f"Pack '{pack_id}' retrieval must be a mapping")

    tool_section = section.get("tool")
    if not isinstance(tool_section, Mapping):
        raise PackConfigError(f"Pack '{pack_id}' retrieval.tool must be a mapping")

    tool_name = tool_section.get("name")
    tool_description = tool_section.get("description")
    if not isinstance(tool_name, str) or not isinstance(tool_description, str):
        raise PackConfigError(
            f"Pack '{pack_id}' retrieval.tool.name/description must be strings"
        )

    search_kwargs = section.get("search_kwargs")
    if search_kwargs is not None:
        if not isinstance(search_kwargs, MutableMapping):
            raise PackConfigError(
                f"Pack '{pack_id}' retrieval.search_kwargs must be a mapping when provided"
            )
        search_kwargs = dict(search_kwargs)

    llm_intent_query_retrieval = bool(section.get("llm_intent_query_retrieval", True))

    hybrid_section = section.get("hybrid")
    if hybrid_section is None:
        hybrid_config = HybridRetrievalConfig()
    else:
        if not isinstance(hybrid_section, Mapping):
            raise PackConfigError(
                f"Pack '{pack_id}' retrieval.hybrid must be a mapping when provided"
            )
        hybrid_config = HybridRetrievalConfig(
            enable_bm25=bool(hybrid_section.get("enable_bm25", False)),
            enable_parent_pages=bool(hybrid_section.get("enable_parent_pages", False)),
        )

    return RetrievalConfig(
        tool_name=tool_name,
        tool_description=tool_description,
        search_kwargs=search_kwargs,
        hybrid=hybrid_config,
        llm_intent_query_retrieval=llm_intent_query_retrieval,
    )


def _resolve_legacy_retriever(
    pack_id: str, section: Mapping[str, Any]
) -> RetrievalConfig:
    if not isinstance(section, Mapping):
        raise PackConfigError(
            f"Pack '{pack_id}' retriever block must be a mapping for legacy support"
        )

    tool_name = section.get("tool_name")
    tool_description = section.get("tool_description")
    if not isinstance(tool_name, str) or not isinstance(tool_description, str):
        raise PackConfigError(
            f"Pack '{pack_id}' retriever.tool_name/tool_description must be strings"
        )

    search_kwargs = section.get("search_kwargs")
    if search_kwargs is not None:
        if not isinstance(search_kwargs, MutableMapping):
            raise PackConfigError(
                f"Pack '{pack_id}' retriever.search_kwargs must be a mapping when provided"
            )
        search_kwargs = dict(search_kwargs)

    return RetrievalConfig(
        tool_name=tool_name,
        tool_description=tool_description,
        search_kwargs=search_kwargs,
    )


def _resolve_chunking(payload: Mapping[str, Any]) -> ChunkingConfig:
    chunk_section = payload.get("chunking")
    if chunk_section is None:
        return ChunkingConfig()
    if not isinstance(chunk_section, Mapping):
        raise PackConfigError("chunking section must be a mapping if provided")

    size = chunk_section.get("size", DEFAULT_CHUNK_SIZE)
    overlap = chunk_section.get("overlap", DEFAULT_CHUNK_OVERLAP)

    if not isinstance(size, int) or not isinstance(overlap, int):
        raise PackConfigError("chunking.size/overlap must be integers")

    return ChunkingConfig(size=size, overlap=overlap)


def _resolve_rerank(pack_id: str, payload: Mapping[str, Any]) -> RerankConfig | None:
    rerank_section = payload.get("rerank")
    if rerank_section is None:
        return None

    if not isinstance(rerank_section, Mapping):
        raise PackConfigError(f"Pack '{pack_id}' rerank must be a mapping or null")

    provider = rerank_section.get("provider")
    provider_value: RerankProvider | str | None = None
    if provider is not None:
        if not isinstance(provider, str):
            raise PackConfigError(
                f"Pack '{pack_id}' rerank.provider must be a string, received: {type(provider)!r}"
            )
        try:
            provider_value = RerankProvider(provider.lower())
        except ValueError:
            provider_value = provider

    return RerankConfig(
        provider=provider_value,
        model=rerank_section.get("model"),
        model_env=rerank_section.get("model_env"),
        api_key=rerank_section.get("api_key"),
        api_key_env=rerank_section.get("api_key_env"),
        endpoint=rerank_section.get("endpoint"),
        top_k=rerank_section.get("top_k"),
        candidate_k=rerank_section.get("candidate_k"),
        timeout=rerank_section.get("timeout"),
        extra=rerank_section.get("extra", {}),
        fallback_envs=tuple(rerank_section.get("fallback_envs", ())),
    )


def build_pack_from_config(pack_id: str) -> KnowledgePack:
    """Construct a KnowledgePack instance from YAML configuration."""

    payload = load_pack_document(pack_id)

    metadata_section = payload.get("metadata")
    if not isinstance(metadata_section, Mapping):
        raise PackConfigError("pack configuration must include a 'metadata' mapping")

    declared_pack_id = metadata_section.get("pack_id")
    if declared_pack_id and declared_pack_id != pack_id:
        raise PackConfigError(
            f"Pack '{pack_id}' configuration declares mismatched pack_id '{declared_pack_id}' in metadata"
        )

    display_name = metadata_section.get("display_name")
    description = metadata_section.get("description")
    if not isinstance(display_name, str) or not isinstance(description, str):
        raise PackConfigError(
            f"Pack '{pack_id}' metadata.display_name/description must be strings"
        )

    base_dir = PACKS_DIR / pack_id
    generate_response = _resolve_generate_response_config(pack_id, payload, base_dir)
    grader_rewrite = _resolve_grader_rewrite_config(
        pack_id,
        payload,
        base_dir,
        legacy_rewrite_prompt=None,
        legacy_grade_prompt=None,
    )
    retrieval_config = _resolve_retrieval(pack_id, payload)
    preprocess_config = _resolve_preprocess(payload)
    chunking_config = _resolve_chunking(payload)

    embedding_config = _resolve_embedding_config(pack_id, payload, base_dir)
    rerank_config = _resolve_rerank(pack_id, payload)

    legacy_enable_bm25 = payload.get("enable_bm25")
    if legacy_enable_bm25 is not None:
        retrieval_config.hybrid.enable_bm25 = bool(legacy_enable_bm25)
    legacy_enable_parent_pages = payload.get("enable_parent_pages")
    if legacy_enable_parent_pages is not None:
        retrieval_config.hybrid.enable_parent_pages = bool(legacy_enable_parent_pages)

    return KnowledgePack(
        metadata=PackMetadataConfig(
            pack_id=pack_id,
            display_name=display_name,
            description=description,
        ),
        preprocess=preprocess_config,
        chunking=chunking_config,
        generate_response=generate_response,
        retrieval=retrieval_config,
        embedding=embedding_config,
        rerank_config=rerank_config,
        grader_rewrite=grader_rewrite,
    )


__all__ = [
    "PackConfigError",
    "discover_configured_pack_ids",
    "load_pack_document",
    "build_pack_from_config",
]
