"""
EmergencyOperator - 紧急情况处理 Operator

处理 Agent 宪法层拦截的紧急情况。
"""

from typing import Any, Dict

from langchain_core.messages import AIMessage
from langgraph.runtime import Runtime

from ..core import AgentInvariants, MouthCavityV2State


def emergency_operator(
    state: MouthCavityV2State,
    runtime: Runtime,
) -> Dict[str, Any]:
    """
    紧急情况处理 Operator

    Args:
        state: 当前状态
        runtime: 运行时上下文

    Returns:
        Dict: 状态更新
    """
    logger = getattr(runtime.context, "logger", None)

    if logger:
        logger.warning("🚨 Emergency Operator 触发")

    action_params = state.get("action_params", {})
    message = action_params.get("message", "")
    emergency_type = state.get("emergency_type", "")

    if not message:
        message = (
            "⚠️ 检测到紧急情况！\n\n"
            "根据您描述的症状，这可能是需要紧急处理的情况。\n\n"
            "**请立即**：\n"
            "1. 保持冷静，如有陪同人员请告知他们您的情况\n"
            "2. 拨打 120 或前往最近的急诊\n"
            "3. 如有呼吸困难，保持侧卧位\n\n"
            "🚨 请立即寻求专业医疗帮助！"
        )

    # 构建 AIMessage
    additional_kwargs: Dict[str, Any] = {
        "emergency": True,
        "emergency_type": emergency_type,
    }

    return {
        "messages": [
            AIMessage(
                content=message,
                additional_kwargs=additional_kwargs,
            )
        ],
        "is_emergency": True,
        "risk_level": "HIGH",
        "triage_complete": True,
    }
