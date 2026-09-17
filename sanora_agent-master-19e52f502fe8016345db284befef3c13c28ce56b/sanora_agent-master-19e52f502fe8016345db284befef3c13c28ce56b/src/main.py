import os
import time
from fastapi import FastAPI, HTTPException, Request, Header, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
from typing import Optional

from .config import config
from .models import (
    ChatRequest,
    ModelsResponse,
    ModelInfo,
    QAPairCreateRequest,
    RebuildTarget,
    RebuildRequest,
)
from .chat_service import chat_service
from .logging_config import LoggingConfig
from .observability import init_phoenix_tracing, shutdown_phoenix_tracing

# 初始化日志系统（如果尚未初始化）
if LoggingConfig.LOG_DIR is None:
    LoggingConfig.initialize()

# 获取系统级日志记录器
logger = LoggingConfig.get_system_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    logger.info("Starting OpenAI Compatible API Server...")
    logger.info(f"Available models: {config.list_available_models()}")

    # 初始化 Phoenix 追踪 (在应用启动时)
    init_phoenix_tracing()

    yield

    # 关闭 Phoenix 追踪 (在应用关闭时)
    shutdown_phoenix_tracing()
    logger.info("Shutting down...")


# Create FastAPI app
app = FastAPI(
    title="OpenAI Compatible API Server",
    description="FastAPI + LangGraph implementation of OpenAI Chat Completions API",
    version="1.0.0",
    lifespan=lifespan,
)

# Instrument FastAPI for OpenTelemetry tracing (必须在添加中间件之前)
try:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    FastAPIInstrumentor.instrument_app(app)
    logger.debug("✓ FastAPI instrumented for OpenTelemetry tracing")
except ImportError:
    logger.debug("FastAPI instrumentation not available")
except Exception as e:
    logger.warning(f"Failed to instrument FastAPI: {e}")

# Add CORS middleware
if config.api.enable_cors:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.api.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# Rate limiting middleware (simplified)
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    response = await call_next(request)
    return response


# Trace ID middleware - 添加 trace_id 到响应头
@app.middleware("http")
async def trace_id_middleware(request: Request, call_next):
    """添加 OpenTelemetry trace_id 到响应头，便于测试框架追踪"""
    response = await call_next(request)

    try:
        from opentelemetry import trace
        current_span = trace.get_current_span()
        if current_span and current_span.get_span_context().is_valid:
            trace_id = format(current_span.get_span_context().trace_id, '032x')
            response.headers['X-Trace-ID'] = trace_id
            logger.debug(f"Added trace_id to response: {trace_id}")
    except Exception as e:
        logger.debug(f"Failed to add trace_id to response: {e}")

    return response


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "available_models": config.list_available_models(),
    }


# OpenAI compatible endpoints
@app.get("/v1/models")
async def list_models() -> ModelsResponse:
    """List available models"""
    try:
        models_data = chat_service.get_available_models()
        return ModelsResponse(data=models_data)
    except Exception as e:
        logger.error(f"Error listing models: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/v1/langgraph/apps")
async def list_langgraph_apps():
    """List available LangGraph applications"""
    try:
        apps = chat_service.get_available_graphs()
        enabled_apps = config.list_enabled_langgraph_apps()

        result = []
        for app_id, app_config in enabled_apps.items():
            result.append(
                {
                    "id": app_id,
                    "name": app_config.name,
                    "description": app_config.description,
                    "graph_type": app_config.graph_type,
                    "model_provider": app_config.model_provider,
                    "enabled": app_config.enabled,
                }
            )

        return {"langgraph_apps": result}
    except Exception as e:
        logger.error(f"Error listing LangGraph apps: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/v1/admin/draw-graph")
async def draw_graph_endpoint(authorization: Optional[str] = Header(None)):
    """
    Draws the graph for a given app_id and saves it to a file.
    Requires admin API key.
    """
    try:
        app_id, app_config = chat_service.validate_stream_request(None, authorization)
        chat_service.draw_graph(app_id)
        return {"message": f"Graph for app '{app_id}' drawn successfully."}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error drawing graph for app '{app_id}': {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/v1/chat/completions")
async def chat_completions(
    request: ChatRequest, authorization: Optional[str] = Header(None)
):
    """OpenAI compatible chat completions endpoint"""
    logger.debug(f"++++++++++++++++++++++++++++++++++{request}")
    try:
        if not request.messages:
            raise HTTPException(status_code=400, detail="Messages cannot be empty")

        if request.stream:
            app_id, app_config = chat_service.validate_stream_request(
                request, authorization
            )

            return StreamingResponse(
                chat_service.stream_chat_completions(
                    request, authorization, app_id, app_config
                ),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Transfer-Encoding": "chunked",
                },
            )
        else:
            return await chat_service.chat_completions(request, authorization)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat completion error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/chat/completions")
async def chat_completions_no_version(
    request: ChatRequest, authorization: Optional[str] = Header(None)
):
    """Alternative endpoint without version prefix"""
    return await chat_completions(request, authorization)


@app.post("/v1/cancel/{session_id}")
async def cancel_session(session_id: str, authorization: Optional[str] = Header(None)):
    """
    取消指定会话的正在进行的任务

    Args:
        session_id: 会话ID（通常是设备ID或用户ID）
        authorization: API密钥认证

    Returns:
        取消结果
    """
    try:
        # 验证授权并获取 app_id
        app_id, app_config = chat_service.authenticate_request(authorization)

        # 导入 langgraph_manager
        from .llm_service import langgraph_manager

        # 获取对应的 graph 并取消任务
        graph = langgraph_manager.get_graph(app_id)

        if not graph:
            raise HTTPException(status_code=404, detail=f"未找到应用: {app_id}")

        # 调用 graph 的取消方法
        success = await graph.cancel_task(session_id)

        if success:
            return {
                "status": "success",
                "message": f"会话 {session_id} 的任务已取消",
                "session_id": session_id,
                "app_id": app_id,
            }
        else:
            return {
                "status": "no_active_task",
                "message": f"会话 {session_id} 没有正在运行的任务",
                "session_id": session_id,
                "app_id": app_id,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取消会话任务错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="取消任务失败")


@app.get("/v1/active_sessions")
async def get_active_sessions(authorization: Optional[str] = Header(None)):
    """
    获取指定应用的所有活跃会话

    Args:
        authorization: API密钥认证

    Returns:
        活跃会话列表
    """
    try:
        # 验证授权并获取 app_id
        app_id, app_config = chat_service.authenticate_request(authorization)

        # 导入 langgraph_manager
        from .llm_service import langgraph_manager

        # 获取对应的 graph
        graph = langgraph_manager.get_graph(app_id)

        if not graph:
            raise HTTPException(status_code=404, detail=f"未找到应用: {app_id}")

        # 获取活跃会话信息
        async with graph._task_lock:
            active_sessions = [
                {
                    "session_id": tid,
                    "is_done": task.done(),
                    "is_cancelled": task.cancelled(),
                }
                for tid, task in graph._active_tasks.items()
            ]

        return {
            "app_id": app_id,
            "active_count": len(active_sessions),
            "sessions": active_sessions,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取活跃会话错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取活跃会话失败")


# ==================== 知识库管理 API ====================


@app.get("/v1/knowledge/{pack_id}/documents/{file_name}/chunks")
async def get_document_chunks(pack_id: str, file_name: str):
    """
    获取文档的切片信息（符合 Sheld Server 期望格式）

    Args:
        pack_id: 知识包 ID（如 "sheld_qa"）
        file_name: 文件名（如 "policy.pdf"）

    Returns:
        {
          "success": true,
          "code": 200,
          "message": "获取文档分段信息成功",
          "data": {
            "file_name": "policy.pdf",
            "pack_id": "sheld_qa",
            "document_info": {...},
            "chunking_config": {...},
            "chunks": [...]
          }
        }
    """
    try:
        from src.graphs.knowledge.api import knowledge_doc_service

        result = knowledge_doc_service.get_document_chunks(pack_id, file_name)

        if not result:
            return {
                "success": False,
                "code": 404,
                "message": "文档未找到或未处理",
                "data": None,
                "error": {
                    "error_code": "DOCUMENT_NOT_FOUND",
                    "details": f"文件 '{file_name}' 在知识包 '{pack_id}' 中未找到或尚未进行切片处理",
                },
            }

        return {
            "success": True,
            "code": 200,
            "message": "获取文档分段信息成功",
            "data": result,
        }
    except Exception as e:
        logger.error(f"Error getting document chunks: {e}", exc_info=True)
        return {
            "success": False,
            "code": 500,
            "message": "服务器内部错误",
            "data": None,
            "error": {"error_code": "INTERNAL_ERROR", "details": str(e)},
        }


@app.post("/v1/knowledge/{pack_id}/rebuild")
async def rebuild_knowledge_pack(
    pack_id: str,
    request: RebuildRequest = None,
    authorization: Optional[str] = Header(None),
):
    """
    重建知识库并热更新 Graph（无需重启服务）

    使用场景：
    - Sheld Server 上传新文档后调用
    - 文档内容更新后手动触发

    流程：
    1. 清除缓存配置（强制重建向量库）
    2. 重新构建知识库（向量化 + 切片元数据）
    3. 热更新 Graph 实例（无需重启服务）

    参数：
    - target: 重建目标 (documents/qa_pairs/all)
    - knowledge_base_path: 动态指定文档路径（可选），覆盖 pack.yaml 配置
    """
    # 处理请求体为空的情况
    if request is None:
        request = RebuildRequest()
    target = request.target.value
    knowledge_base_path = request.knowledge_base_path
    try:
        from src.graphs.knowledge import KnowledgePackRegistry
        from src.llm_service import langgraph_manager
        from datetime import datetime

        logger.info(
            f"🔨 开始重建知识包: {pack_id}, 目标: {target}, 文档路径: {knowledge_base_path or '使用配置默认值'}"
        )

        # 1. 验证 pack 存在
        try:
            pack = KnowledgePackRegistry.create(pack_id)
        except Exception as e:
            return {
                "success": False,
                "code": 404,
                "message": f"知识包 '{pack_id}' 不存在",
                "data": None,
                "error": {"error_code": "PACK_NOT_FOUND", "details": str(e)},
            }

        # 注意：动态路径覆盖在 AgenticKnowledgeGraph.__init__ 中处理
        # knowledge_base_path 会通过 reload_graph -> create_graph -> AgenticKnowledgeGraph 传递

        # 2. 根据 target 清除缓存并重建
        cache_dir = pack.embedding.cache_dir

        # 2.1 处理文档重建
        if target in ["documents", "all"]:
            config_path = cache_dir / "config.json"
            if config_path.exists():
                config_path.unlink()
                logger.info(f"已清除文档缓存配置: {config_path}")

        # 2.2 处理问答对重建
        if target in ["qa_pairs", "all"]:
            from src.graphs.knowledge.stores.qa_vector_store import (
                rebuild_qa_vectorstore,
            )

            # 删除旧的 QA 向量索引（强制重建）
            qa_index_file = cache_dir / "qa_faiss_index.faiss"
            qa_pkl_file = cache_dir / "qa_faiss_index.pkl"

            if qa_index_file.exists():
                qa_index_file.unlink()
                logger.info(f"已清除问答对索引: {qa_index_file}")
            if qa_pkl_file.exists():
                qa_pkl_file.unlink()
                logger.info(f"已清除问答对存储: {qa_pkl_file}")

            # 重建问答对向量库
            try:
                qa_vectorstore = rebuild_qa_vectorstore(
                    pack_id=pack_id,
                    cache_dir=cache_dir,
                    embedding_model=pack.embedding.model_key,
                    embedding_factory=pack.embedding.factory,
                )
                if qa_vectorstore:
                    logger.info(f"✅ 问答对向量库重建完成")
                else:
                    logger.warning(f"⚠️  没有问答对需要向量化")
            except Exception as e:
                logger.error(f"❌ 问答对向量库重建失败: {e}", exc_info=True)
                # 问答对重建失败不影响整体流程，继续执行

        # 3. 查找对应的 app_id
        app_id = None
        enabled_apps = config.list_enabled_langgraph_apps()

        for aid, app_config in enabled_apps.items():
            if app_config.graph_type == f"{pack_id}_knowledge":
                app_id = aid
                break

        if not app_id:
            return {
                "success": False,
                "code": 404,
                "message": f"未找到知识包 '{pack_id}' 对应的应用",
                "data": None,
                "error": {
                    "error_code": "APP_NOT_FOUND",
                    "details": f"请确保 config.yaml 中已配置 {pack_id}_knowledge 应用",
                },
            }

        # 4. 重新加载 Graph（会触发向量库重建，传递动态路径）
        success = langgraph_manager.reload_graph(
            app_id, knowledge_base_path=knowledge_base_path
        )

        if not success:
            return {
                "success": False,
                "code": 500,
                "message": "重建知识库失败",
                "data": None,
                "error": {"error_code": "REBUILD_FAILED"},
            }

        # 5. 获取统计信息
        rebuilt_graph = langgraph_manager.get_graph(app_id)
        stats = {}

        if hasattr(rebuilt_graph, 'retriever_resources'):
            resources = rebuilt_graph.retriever_resources

            # 文档统计
            if resources and resources.vectorstore:
                try:
                    from src.graphs.knowledge.stores.vector_store import (
                        collect_vectorstore_documents,
                    )

                    docs = collect_vectorstore_documents(resources.vectorstore)
                    stats["total_document_chunks"] = len(docs)
                except Exception:
                    pass

            # 问答对统计
            if resources and resources.qa_vectorstore:
                try:
                    from src.graphs.knowledge.stores.vector_store import (
                        collect_vectorstore_documents,
                    )

                    qa_docs = collect_vectorstore_documents(resources.qa_vectorstore)
                    stats["total_qa_pairs"] = len(qa_docs)
                except Exception:
                    pass

        return {
            "success": True,
            "code": 200,
            "message": f"知识包 '{pack_id}' 重建成功 (目标: {target})",
            "data": {
                "pack_id": pack_id,
                "app_id": app_id,
                "target": target,
                "rebuilt_at": datetime.now().isoformat(),
                "stats": stats,
            },
        }

    except Exception as e:
        logger.error(f"重建知识库失败: {e}", exc_info=True)
        return {
            "success": False,
            "code": 500,
            "message": f"服务器内部错误: {str(e)}",
            "data": None,
        }


@app.post("/v1/knowledge/{pack_id}/qa_pairs/simple")
async def create_qa_pair_simple(pack_id: str, request: QAPairCreateRequest):
    """
    创建问答对（简化版，不需要 KnowledgePack，仅用于测试）

    跳过：
    - pack 验证
    - 向量化

    仅保存 JSON
    """
    try:
        from src.graphs.knowledge.stores.qa_store import QAPairStore
        from pathlib import Path

        logger.info(f"📝 [简化版] 保存问答对到: {pack_id}")

        # 直接使用固定路径
        cache_dir = Path(f"src/graphs/knowledge/packs/{pack_id}/vector_cache")
        cache_dir.mkdir(parents=True, exist_ok=True)

        # 保存问答对到 JSON
        qa_store = QAPairStore(pack_id=pack_id, cache_dir=cache_dir)

        session_id = request.session_id or f"auto-{int(time.time())}"

        qa_pair = qa_store.add(
            question=request.question,
            answer=request.answer,
            session_id=session_id,
            metadata=request.metadata,
        )

        logger.info(f"✅ [简化版] 问答对已保存: {qa_pair.qa_id}")

        return {
            "success": True,
            "code": 200,
            "message": "问答对保存成功（简化版：仅保存JSON，未向量化）",
            "data": {
                "qa_id": qa_pair.qa_id,
                "pack_id": qa_pair.pack_id,
                "created_at": qa_pair.created_at,
            },
        }

    except Exception as e:
        logger.error(f"[简化版] 保存问答对失败: {e}", exc_info=True)
        return {
            "success": False,
            "code": 500,
            "message": f"服务器内部错误: {str(e)}",
            "data": None,
            "error": {"error_code": "INTERNAL_ERROR", "details": str(e)},
        }


@app.post("/v1/knowledge/{pack_id}/qa_pairs")
async def create_qa_pair(
    pack_id: str,
    request: QAPairCreateRequest,
    authorization: Optional[str] = Header(None),
):
    """
    创建并保存问答对到知识库

    使用场景：
    - Sheld 前端用户点击确认按钮，保存满意的问答对
    - 问答对将被向量化并用于后续检索

    Args:
        pack_id: 知识包 ID（如 "sheld_qa"）
        request: 问答对创建请求
        authorization: API密钥认证（可选）

    Returns:
        {
          "success": true,
          "code": 200,
          "message": "问答对保存成功",
          "data": {
            "qa_id": "uuid",
            "pack_id": "sheld_qa",
            "created_at": "2025-11-18T10:00:00"
          }
        }
    """
    try:
        from src.graphs.knowledge import KnowledgePackRegistry
        from src.graphs.knowledge.stores.qa_store import QAPairStore
        from src.graphs.knowledge.stores.qa_vector_store import QAVectorStore

        logger.info(f"📝 保存问答对到知识包: {pack_id}")

        # 1. 验证 pack 存在
        try:
            pack = KnowledgePackRegistry.create(pack_id)
        except Exception as e:
            return {
                "success": False,
                "code": 404,
                "message": f"知识包 '{pack_id}' 不存在",
                "data": None,
                "error": {"error_code": "PACK_NOT_FOUND", "details": str(e)},
            }

        cache_dir = pack.embedding.cache_dir
        cache_dir.mkdir(parents=True, exist_ok=True)

        # 2. 保存问答对到 JSON
        qa_store = QAPairStore(pack_id=pack_id, cache_dir=cache_dir)

        # 如果没有提供 session_id，生成一个默认值
        session_id = request.session_id or f"auto-{int(time.time())}"

        qa_pair = qa_store.add(
            question=request.question,
            answer=request.answer,
            session_id=session_id,
            metadata=request.metadata,
            editor_id=request.editor_id,
            editor_name=request.editor_name,
            edited_at=request.edited_at,
        )

        logger.info(f"✅ 问答对已保存: {qa_pair.qa_id}（需调用 rebuild 生效）")

        return {
            "success": True,
            "code": 200,
            "message": "问答对保存成功",
            "data": {
                "qa_id": qa_pair.qa_id,
                "pack_id": qa_pair.pack_id,
                "created_at": qa_pair.created_at,
            },
        }

    except Exception as e:
        logger.error(f"保存问答对失败: {e}", exc_info=True)
        return {
            "success": False,
            "code": 500,
            "message": f"服务器内部错误: {str(e)}",
            "data": None,
            "error": {"error_code": "INTERNAL_ERROR", "details": str(e)},
        }


@app.get("/v1/knowledge/{dataset}/qa_pairs")
async def get_qa_pairs_list(dataset: str):
    """
    获取知识包的所有问答对列表

    Args:
        dataset: 知识包 ID（如 "sheld_qa"）

    Returns:
        {
          "success": true,
          "code": 200,
          "message": "获取问答对列表成功",
          "data": {
            "pack_id": "sheld_qa",
            "total_count": 5,
            "qa_pairs": {
              "qa_id_1": { "qa_id": "...", "question": "...", "editor_name": "...", ... },
              "qa_id_2": { ... }
            }
          }
        }
    """
    try:
        from src.graphs.knowledge import KnowledgePackRegistry
        from src.graphs.knowledge.stores.qa_store import load_qa_pairs

        logger.info(f"📋 获取问答对列表: {dataset}")

        # 1. 验证 pack 存在
        try:
            pack = KnowledgePackRegistry.create(dataset)
        except Exception as e:
            return {
                "success": False,
                "code": 404,
                "message": f"知识包 '{dataset}' 不存在",
                "data": None,
                "error": {"error_code": "PACK_NOT_FOUND", "details": str(e)},
            }

        cache_dir = pack.embedding.cache_dir
        qa_pairs_path = cache_dir / "qa_pairs.json"

        # 2. 加载问答对
        collection = load_qa_pairs(qa_pairs_path)

        if collection is None:
            return {
                "success": True,
                "code": 200,
                "message": "问答对列表为空",
                "data": {"pack_id": dataset, "total_count": 0, "qa_pairs": {}},
            }

        # 3. 转换为字典格式
        qa_pairs_dict = {
            qa_id: qa.to_dict() for qa_id, qa in collection.qa_pairs.items()
        }

        return {
            "success": True,
            "code": 200,
            "message": "获取问答对列表成功",
            "data": {
                "pack_id": dataset,
                "total_count": len(qa_pairs_dict),
                "qa_pairs": qa_pairs_dict,
            },
        }

    except Exception as e:
        logger.error(f"获取问答对列表失败: {e}", exc_info=True)
        return {
            "success": False,
            "code": 500,
            "message": f"服务器内部错误: {str(e)}",
            "data": None,
            "error": {"error_code": "INTERNAL_ERROR", "details": str(e)},
        }


# ── 生成文件下载接口 ─────────────────────────────────────────────────────────
_NEO_OUTPUT_DIR = os.environ.get("NEO_OUTPUT_DIR", "/tmp/rooyee_generated")


@app.get("/v1/files/{filename}")
async def download_generated_file(filename: str):
    """
    下载 Neo Graph 生成的文件（xlsx 等）。
    URL 示例：/v1/files/出差報告_20260310_abc123.xlsx
    """
    # 防止路径穿越
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="非法文件名")

    file_path = os.path.join(_NEO_OUTPUT_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"文件不存在: {filename}")

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/octet-stream",
    )


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "OpenAI Compatible API Server",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "models": "/v1/models",
            "chat_completions": "/v1/chat/completions",
            "langgraph_apps": "/v1/langgraph/apps",
            "cancel_session": "/v1/cancel/{session_id}",
            "active_sessions": "/v1/active_sessions",
            "knowledge_chunks": "/v1/knowledge/{pack_id}/documents/{file_name}/chunks",
            "knowledge_rebuild": "/v1/knowledge/{pack_id}/rebuild",
            "qa_pairs_create": "/v1/knowledge/{pack_id}/qa_pairs [POST]",
            "qa_pairs_list": "/v1/knowledge/{dataset}/qa_pairs [GET]",
        },
        "available_models": config.list_available_models(),
    }


def create_app() -> FastAPI:
    """Factory function to create the FastAPI app"""
    return app


if __name__ == "__main__":
    host = config._config_data.get("server", {}).get("host", "0.0.0.0")
    port = config._config_data.get("server", {}).get("port", 8000)

    uvicorn.run(
        "src.main:app",
        host=host,
        port=port,
        reload=True,
        log_level="info",
        limit_max_requests=10000,  # 最大请求数
        timeout_keep_alive=30,  # Keep-alive 超时
    )
