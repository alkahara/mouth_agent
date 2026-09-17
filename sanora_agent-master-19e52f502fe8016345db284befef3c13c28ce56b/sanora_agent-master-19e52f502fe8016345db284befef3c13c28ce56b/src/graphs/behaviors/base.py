from __future__ import annotations

import time
import uuid
from typing import Optional

from ...models import ChatResponse, Choice, Message, MessageRole, Usage


class GraphBehavior:
    """Base behavior hooks for LangGraph applications."""

    def preprocess(self, request, graph, app_config, thread_id: str) -> Optional[ChatResponse]:
        """Pre-processing hook before running the graph.

        Return a ChatResponse to short-circuit normal processing, or None to continue.
        """

        return None

    def should_reset(self, request, graph, app_config, thread_id: str) -> bool:
        """Whether the current request should trigger a state reset."""

        return getattr(request, "reset_state", False)

    def on_reset(self, request, graph, app_config, thread_id: str) -> Optional[ChatResponse]:
        """Called after the state has been cleared; return a response if needed."""

        return None

    def initial_response(
        self, request, graph, app_config, thread_id: str
    ) -> Optional[ChatResponse]:
        """Optional initial response before graph execution (e.g., greetings)."""

        return None

    def on_state_cleared(self, thread_id: str) -> None:
        """Hook invoked after reset to clear behavior-specific cache."""

    def build_text_response(
        self,
        request,
        text: str,
        app_config,
        *,
        thread_id: Optional[str] = None,
        record_welcome: bool = False,
    ) -> ChatResponse:
        """Helper to build a simple ChatResponse containing a single assistant message."""

        model = request.model or getattr(app_config, "model_provider", "")
        response_id = f"chatcmpl-{uuid.uuid4().hex}"
        created = int(time.time())
        response = ChatResponse(
            id=response_id,
            created=created,
            model=model,
            choices=[
                Choice(
                    index=0,
                    message=Message(role=MessageRole.ASSISTANT, content=text),
                    finish_reason="stop",
                )
            ],
            usage=Usage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
        )

        if record_welcome and thread_id and hasattr(self, "_welcomed_threads"):
            try:
                self._welcomed_threads.add(thread_id)  # type: ignore[attr-defined]
            except Exception:  # noqa: BLE001
                pass

        return response


class DefaultGraphBehavior(GraphBehavior):
    """No-op behavior for graphs that rely on default handling."""

    pass
