"""
FallbackOperator - 兜底处理 Operator

处理无法识别的情况。
"""

from typing import Any, Dict

from langchain_core.messages import AIMessage
from langgraph.runtime import Runtime

from ..core import MouthCavityV2State


def fallback_operator(
    state: MouthCavityV2State,
    runtime: Runtime,
) -> Dict[str, Any]:
    """
    兜底处理 Operator

    Args:
        state: 当前状态
        runtime: 运行时上下文

    Returns:
        Dict: 状态更新
    """
    logger = getattr(runtime.context, "logger", None)

    if logger:
        logger.info("❓ Fallback Operator 触发")

    action_params = state.get("action_params", {})
    message = action_params.get("message", "")

    if not message:
        message = (
            "抱歉，我暂时无法理解您的问题。\n\n"
            "您可以尝试：\n"
            "1. 更详细地描述您的情况\n"
            "2. 告诉我您目前遇到的具体问题\n\n"
            "如果您有紧急情况，请直接联系医生或拨打 120。"
        )

    return {
        "messages": [AIMessage(content=message)],
    }
