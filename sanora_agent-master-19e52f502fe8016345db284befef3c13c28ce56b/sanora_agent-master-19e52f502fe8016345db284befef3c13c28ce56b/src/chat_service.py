import json
import time
import uuid
import asyncio
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple
from fastapi import HTTPException
import logging

from .models import (
    ChatRequest,
    ChatResponse,
    ChatStreamResponse,
    Choice,
    Message,
    Usage,
    MessageRole,
)
from .llm_service import langgraph_manager, llm_provider
from .config import config, LangGraphAppConfig
from .graphs.behaviors import GraphBehaviorRegistry
from .logging_config import LoggingConfig

logger = logging.getLogger(__name__)


class ChatService:
    """Chat completion service with multi-graph support"""

    def __init__(self):
        self.active_requests = 0
        self.max_concurrent = config.server.max_concurrent_requests

    def authenticate_request(
        self, authorization_header: Optional[str]
    ) -> Tuple[str, LangGraphAppConfig]:
        """Authenticate request and return app info"""
        if not authorization_header:
            if config.auth.default_fallback:
                # Use default graph
                default_app_id = config.get_default_graph()
                app_config = config.get_langgraph_app(default_app_id)
                if app_config and app_config.enabled:
                    return default_app_id, app_config
            raise HTTPException(status_code=401, detail="Authorization header required")

        # Extract Bearer token
        if not authorization_header.startswith("Bearer "):
            raise HTTPException(
                status_code=401,
                detail="Invalid authorization header format. Use 'Bearer <token>'",
            )

        api_key = authorization_header[7:]  # Remove "Bearer " prefix

        # Authenticate API key
        result = langgraph_manager.authenticate_request(api_key)
        if not result:
            raise HTTPException(status_code=401, detail="Invalid API key")

        return result

    def draw_graph(self, app_id: str):
        """Draw the graph for a given app_id and save to file"""
        graph = langgraph_manager.get_graph(app_id)
        if not graph:
            raise HTTPException(status_code=404, detail=f"Graph {app_id} not found")
        graph.draw_graph()
        logger.info(f"Graph for app {app_id} drawn successfully.")
        return

    async def chat_completions(
        self, request: ChatRequest, authorization_header: Optional[str] = None
    ) -> ChatResponse:
        """Handle non-streaming chat completions"""
        await self._check_rate_limit()

        # Authenticate and get app info
        app_id, app_config = self.authenticate_request(authorization_header)

        # Get the appropriate graph
        graph = langgraph_manager.get_graph(app_id)
        if not graph:
            raise HTTPException(status_code=500, detail=f"Graph {app_id} not available")

        behavior = GraphBehaviorRegistry.get_behavior(app_config.graph_type)
        thread_id = request.thread_id or request.user or "default-thread"

        # Behavior-specific preprocessing (e.g., scope checks)
        pre_response = behavior.preprocess(
            request=request,
            graph=graph,
            app_config=app_config,
            thread_id=thread_id,
        )
        if pre_response:
            return pre_response

        # Reset handling
        if behavior.should_reset(
            request=request,
            graph=graph,
            app_config=app_config,
            thread_id=thread_id,
        ):
            await self._reset_graph_state(graph, request, app_id, behavior, thread_id)
            reset_response = behavior.on_reset(
                request=request,
                graph=graph,
                app_config=app_config,
                thread_id=thread_id,
            )
            if reset_response:
                return reset_response
        else:
            init_response = behavior.initial_response(
                request=request,
                graph=graph,
                app_config=app_config,
                thread_id=thread_id,
            )
            if init_response:
                return init_response

        try:
            self.active_requests += 1

            # Generate chat ID
            chat_id = f"chatcmpl-{uuid.uuid4().hex}"
            created = int(time.time())

            # Set model from app config if not specified
            if not request.model:
                request.model = app_config.model_provider
            logger.debug(f"Using model: {request.model}")

            # Collect full response
            content_parts = []
            accumulated_additional: Dict[str, Any] = {}
            usage_stats = Usage(prompt_tokens=0, completion_tokens=0, total_tokens=0)

            async for chunk in graph.stream_chat(request, app_id):
                if isinstance(chunk, dict):
                    text_fragment = chunk.get("text") or ""
                    if text_fragment:
                        content_parts.append(text_fragment)
                    additional = chunk.get("additional_kwargs") or {}
                    if additional:
                        accumulated_additional.update(additional)
                    continue

                # Check for usage metadata marker
                if chunk.startswith("__USAGE__") and chunk.endswith("__USAGE__"):
                    # Extract usage metadata
                    usage_str = chunk[9:-9]  # Remove markers
                    try:
                        import ast

                        usage_data = ast.literal_eval(usage_str)
                        if isinstance(usage_data, dict):
                            usage_stats.prompt_tokens = usage_data.get(
                                'input_tokens', 0
                            )
                            usage_stats.completion_tokens = usage_data.get(
                                'output_tokens', 0
                            )
                            usage_stats.total_tokens = usage_data.get('total_tokens', 0)
                            logger.debug(
                                f"Updated usage stats from chunk: {usage_stats}"
                            )
                    except Exception as e:
                        logger.warning(f"Failed to parse usage metadata: {e}")
                else:
                    content_parts.append(chunk)

            content = "".join(content_parts)

            # If no usage stats from chunks, calculate fallback
            if usage_stats.total_tokens == 0:
                prompt_text = " ".join([msg.content for msg in request.messages])
                usage_stats.prompt_tokens = len(prompt_text.split())
                usage_stats.completion_tokens = len(content.split())
                usage_stats.total_tokens = (
                    usage_stats.prompt_tokens + usage_stats.completion_tokens
                )

            # Create response
            response = ChatResponse(
                id=chat_id,
                created=created,
                model=request.model,
                choices=[
                    Choice(
                        index=0,
                        message=Message(
                            role=MessageRole.ASSISTANT,
                            content=content,
                            additional_kwargs=accumulated_additional or None,
                        ),
                        finish_reason="stop",
                    )
                ],
                usage=usage_stats,
            )

            return response

        except Exception as e:
            logger.error(f"Error in chat completion for app {app_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            self.active_requests -= 1

    def validate_stream_request(
        self, request: ChatRequest, authorization_header: Optional[str] = None
    ) -> Tuple[str, LangGraphAppConfig]:
        """Validate streaming request before starting response"""
        # Check rate limiting
        if self.active_requests >= self.max_concurrent:
            raise HTTPException(status_code=429, detail="Too many concurrent requests")

        # Authenticate and get app info
        app_id, app_config = self.authenticate_request(authorization_header)

        # Get the appropriate graph
        graph = langgraph_manager.get_graph(app_id)
        if not graph:
            raise HTTPException(status_code=500, detail=f"Graph {app_id} not available")

        return app_id, app_config

    async def _reset_graph_state(
        self,
        graph,
        request: ChatRequest,
        app_id: str,
        behavior,
        thread_id: str,
    ) -> None:
        """Reset graph state for the provided thread."""
        config = {"configurable": {"thread_id": thread_id}}
        reset_done = False

        if hasattr(graph, "reset_state"):
            try:
                maybe_awaitable = graph.reset_state(config)
                if asyncio.iscoroutine(maybe_awaitable):
                    await maybe_awaitable
                reset_done = True
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Graph %s reset_state failed for thread %s: %s",
                    app_id,
                    thread_id,
                    exc,
                )

        if (
            not reset_done
            and hasattr(graph, "graph")
            and hasattr(graph.graph, "checkpointer")
        ):
            try:
                checkpointer = graph.graph.checkpointer  # type: ignore[attr-defined]
                if hasattr(checkpointer, "delete_thread"):
                    result = checkpointer.delete_thread(thread_id)
                    if asyncio.iscoroutine(result):
                        await result
                elif hasattr(checkpointer, "adelete_thread"):
                    await checkpointer.adelete_thread(thread_id)
                else:
                    raise AttributeError("checkpointer has no delete_thread method")
                reset_done = True
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Checkpointer reset failed for %s thread %s: %s",
                    app_id,
                    thread_id,
                    exc,
                )

        if reset_done:
            logger.info(
                "Reset state for app %s thread_id=%s user=%s",
                app_id,
                thread_id,
                request.user,
            )
        else:
            logger.warning(
                "Graph %s does not support state reset; ignoring reset_state flag",
                app_id,
            )

        behavior.on_state_cleared(thread_id)

    async def stream_chat_completions(
        self,
        request: ChatRequest,
        authorization_header: Optional[str] = None,
        app_id: Optional[str] = None,
        app_config: Optional[LangGraphAppConfig] = None,
    ) -> AsyncGenerator[str, None]:
        """Handle streaming chat completions"""
        # If pre-validated parameters are provided, use them
        if app_id and app_config:
            validated_app_id = app_id
            validated_app_config = app_config
        else:
            # Fallback to validation (for backward compatibility)
            validated_app_id, validated_app_config = self.validate_stream_request(
                request, authorization_header
            )

        # Get the graph (we know it exists from validation)
        graph = langgraph_manager.get_graph(validated_app_id)

        behavior = GraphBehaviorRegistry.get_behavior(  # type: ignore[arg-type]
            validated_app_config.graph_type
        )
        thread_id = request.thread_id or request.user or "default-thread"

        # Preprocess hook (e.g., domain check)
        pre_response = behavior.preprocess(
            request=request,
            graph=graph,
            app_config=validated_app_config,
            thread_id=thread_id,
        )
        if pre_response:
            for chunk in self._stream_simple_response(pre_response):
                yield chunk
            return

        if behavior.should_reset(
            request=request,
            graph=graph,
            app_config=validated_app_config,
            thread_id=thread_id,
        ):
            await self._reset_graph_state(
                graph, request, validated_app_id, behavior, thread_id
            )
            reset_response = behavior.on_reset(
                request=request,
                graph=graph,
                app_config=validated_app_config,
                thread_id=thread_id,
            )
            if reset_response:
                for chunk in self._stream_simple_response(reset_response):
                    yield chunk
                return
        else:
            init_response = behavior.initial_response(
                request=request,
                graph=graph,
                app_config=validated_app_config,
                thread_id=thread_id,
            )
            if init_response:
                for chunk in self._stream_simple_response(init_response):
                    yield chunk
                return

        try:
            chat_start_time = time.time()
            self.active_requests += 1

            # Generate chat ID
            chat_id = f"chatcmpl-{uuid.uuid4().hex}"
            created = int(time.time())
            usage_stats = Usage(prompt_tokens=0, completion_tokens=0, total_tokens=0)

            # Set model from app config if not specified
            if not request.model:
                request.model = validated_app_config.model_provider

            # Calculate prompt tokens (simplified)
            prompt_text = " ".join([msg.content for msg in request.messages])
            usage_stats.prompt_tokens = len(prompt_text.split())

            # Send initial chunk
            initial_chunk = ChatStreamResponse(
                id=chat_id,
                created=created,
                model=request.model,
                choices=[
                    Choice(
                        index=0,
                        delta={"role": "assistant", "content": ""},
                        finish_reason=None,
                    )
                ],
            )
            yield f"data: {json.dumps(initial_chunk.dict())}\n\n"

            # 标记是否遇到中断
            is_interrupted = False
            generated_segments: List[str] = []

            # Stream content chunks
            async for chunk in graph.stream_chat(request, validated_app_id):
                if isinstance(chunk, dict):
                    text_fragment = chunk.get("text") or ""
                    additional = chunk.get("additional_kwargs") or {}

                    if text_fragment:
                        generated_segments.append(text_fragment)
                        stream_chunk = ChatStreamResponse(
                            id=chat_id,
                            created=created,
                            model=request.model,
                            choices=[
                                Choice(
                                    index=0,
                                    delta={"content": text_fragment},
                                    finish_reason=None,
                                )
                            ],
                        )
                        yield f"data: {json.dumps(stream_chunk.dict())}\n\n"

                    if additional:
                        stream_chunk = ChatStreamResponse(
                            id=chat_id,
                            created=created,
                            model=request.model,
                            choices=[
                                Choice(
                                    index=0,
                                    delta={"additional_kwargs": additional},
                                    finish_reason=None,
                                )
                            ],
                        )
                        yield f"data: {json.dumps(stream_chunk.dict())}\n\n"
                    continue

                # Check for interrupt marker
                if chunk.startswith("__INTERRUPT__") and chunk.endswith(
                    "__INTERRUPT__"
                ):
                    # 提取中断信息
                    interrupt_msg = chunk[13:-13]  # Remove markers
                    logger.info(f"Graph interrupted: {interrupt_msg}")

                    # 发送中断状态给客户端
                    interrupt_chunk = ChatStreamResponse(
                        id=chat_id,
                        created=created,
                        model=request.model,
                        choices=[
                            Choice(
                                index=0,
                                delta={"content": interrupt_msg},
                                finish_reason="interrupt",
                            )
                        ],
                    )
                    yield f"data: {json.dumps(interrupt_chunk.dict())}\n\n"
                    is_interrupted = True

                    # 继续消费生成器直到自然结束，但不再输出内容
                    continue

                # 如果已经中断，跳过后续所有内容输出
                if is_interrupted:
                    continue

                # Check for usage metadata marker
                if chunk.startswith("__USAGE__") and chunk.endswith("__USAGE__"):
                    # Extract and update usage metadata
                    usage_str = chunk[9:-9]  # Remove markers
                    try:
                        import ast

                        usage_data = ast.literal_eval(usage_str)
                        if isinstance(usage_data, dict):
                            usage_stats.prompt_tokens += usage_data.get(
                                'input_tokens', 0
                            )
                            usage_stats.completion_tokens += usage_data.get(
                                'output_tokens', 0
                            )
                            usage_stats.total_tokens += usage_data.get(
                                'total_tokens', 0
                            )
                            logger.debug(
                                f"Updated usage stats from chunk: {usage_stats}"
                            )
                    except Exception as e:
                        logger.warning(f"Failed to parse usage metadata: {e}")
                    continue  # Don't send usage metadata to client

                if chunk:  # Only send non-empty content chunks
                    generated_segments.append(chunk)
                    stream_chunk = ChatStreamResponse(
                        id=chat_id,
                        created=created,
                        model=request.model,
                        choices=[
                            Choice(
                                index=0, delta={"content": chunk}, finish_reason=None
                            )
                        ],
                    )
                    yield f"data: {json.dumps(stream_chunk.dict())}\n\n"

            # Send final chunk with usage (only if we have valid usage stats)
            if usage_stats.total_tokens == 0:
                # Fallback calculation if no usage metadata was received
                prompt_text = " ".join([msg.content for msg in request.messages])
                usage_stats.prompt_tokens = len(prompt_text.split())
                completion_text = "".join(generated_segments)
                usage_stats.completion_tokens = len(completion_text.split())
                usage_stats.total_tokens = (
                    usage_stats.prompt_tokens + usage_stats.completion_tokens
                )

            # 根据是否中断设置不同的 finish_reason
            finish_reason = "interrupt" if is_interrupted else "stop"

            final_chunk = ChatStreamResponse(
                id=chat_id,
                created=created,
                model=request.model,
                choices=[Choice(index=0, delta={}, finish_reason=finish_reason)],
                usage=usage_stats,
            )
            yield f"data: {json.dumps(final_chunk.dict())}\n\n"

            # Send DONE signal
            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"Error in streaming chat for app {validated_app_id}: {e}")
            error_chunk = {
                "error": {
                    "message": str(e),
                    "type": "server_error",
                    "code": "internal_error",

                }
            }
            yield f"data: {json.dumps(error_chunk)}\n\n"
            yield "data: [DONE]\n\n"
        finally:
            # 获取图对应的 logger
            graph_logger = LoggingConfig.get_graph_logger(
                graph_type=validated_app_config.graph_type, 
                graph_class_name="ChatService"
            )
            graph_logger.info(
                f"DEBUG_TIMER: ChatService [stream_chat_completions] Total Duration: {time.time() - chat_start_time:.4f}s | Device: {thread_id}"
            )
            self.active_requests -= 1

    async def _check_rate_limit(self):
        """Check rate limiting"""
        if self.active_requests >= self.max_concurrent:
            raise HTTPException(status_code=429, detail="Too many concurrent requests")

    def get_available_models(self) -> list:
        """Get list of available models"""
        models = []

        for provider_name in config.list_available_models():
            if llm_provider.is_available(provider_name):
                model_config = config.get_model_config(provider_name)
                models.append(
                    {
                        "id": model_config.name,
                        "object": "model",
                        "created": int(time.time()),
                        "owned_by": "rooyee",
                        "provider": provider_name,
                    }
                )

        return models

    def _stream_simple_response(self, response: ChatResponse):
        """Utility to send a single ChatResponse via streaming protocol."""

        text = ""
        if response.choices:
            choice = response.choices[0]
            if choice.message and choice.message.content:
                text = choice.message.content
            elif choice.delta and "content" in choice.delta:
                text = choice.delta.get("content", "")

        model = response.model or config.get_default_model()
        chunk = ChatStreamResponse(
            id=response.id or f"chatcmpl-{uuid.uuid4().hex}",
            created=int(time.time()),
            model=model,
            choices=[
                Choice(
                    index=0,
                    delta={"content": text},
                    finish_reason="stop",
                )
            ],
            usage=response.usage,
        )
        yield f"data: {json.dumps(chunk.dict())}\n\n"
        yield "data: [DONE]\n\n"


chat_service = ChatService()
