"""
FinalOperator - 最终响应 Operator

负责生成最终的护理方案和分诊结果。
"""

import json
from pathlib import Path
from typing import Any, Dict

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.runtime import Runtime

from ..core import FlowRegistry, MouthCavityV2State


# Prompt 文件路径
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def _load_prompt(filename: str) -> str:
    """加载 Prompt 文件"""
    path = PROMPTS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8")


def _render_template(template_str: str, **kwargs) -> str:
    """简单模板渲染（使用 {{key}} 替换）"""
    result = template_str
    for key, value in kwargs.items():
        if isinstance(value, (list, dict)):
            value = json.dumps(value, ensure_ascii=False, indent=2)
        elif value is None:
            value = ""
        result = result.replace("{{" + key + "}}", str(value))
    return result


def final_operator(
    state: MouthCavityV2State,
    runtime: Runtime,
) -> Dict[str, Any]:
    """
    最终响应 Operator

    生成最终的护理方案和分诊结果。

    Args:
        state: 当前状态
        runtime: 运行时上下文

    Returns:
        Dict: 状态更新
    """
    logger = getattr(runtime.context, "logger", None)
    get_node_llm = getattr(runtime.context, "get_node_llm", None)

    if logger:
        logger.info("✅ Final Operator 开始")

    action_params = state.get("action_params", {})
    current_flow_id = state.get("current_flow_id", "")
    current_slots = state.get("slots", {})
    patient_emotion = state.get("patient_emotion", "calm")
    debug_mode = state.get("debug_mode", False)

    # 获取风险等级和护理方案 ID
    risk_level = action_params.get("risk_level", state.get("risk_level", ""))
    care_plan_id = action_params.get("care_plan_id", state.get("care_plan_id", ""))
    message = action_params.get("message", "")

    # 如果 Manager 已经提供了消息，直接使用
    video_url = None
    video_password = None

    if message:
        final_response = message
    else:
        # 获取流程实例
        flow = FlowRegistry.get_or_none(current_flow_id)

        if flow and care_plan_id:
            # 获取护理方案
            try:
                care_plan = flow.get_care_plan(care_plan_id, current_slots)
                care_template = care_plan.get("content", "")

                # 提取视频信息
                video_url = care_plan.get("video_url")
                video_password = care_plan.get("video_password")

                # 使用 Prompt 生成最终响应
                prompt_template = _load_prompt("care_plan.md")
                prompt = _render_template(
                    prompt_template,
                    slots_summary=flow.get_slots_summary(current_slots),
                    risk_level=risk_level,
                    care_template=care_template,
                    patient_emotion=patient_emotion,
                )

                if get_node_llm:
                    llm = get_node_llm("final_operator", runtime)
                    response = llm.invoke([HumanMessage(content=prompt)])
                    final_response = response.content
                else:
                    final_response = care_template

            except Exception as e:
                if logger:
                    logger.error(f"生成护理方案失败: {e}")
                final_response = "抱歉，生成护理方案时出现问题。建议您联系医生获取专业指导。"
        else:
            # 没有流程或护理方案 ID
            if risk_level == "HIGH":
                final_response = "根据您描述的情况，建议您尽快前往急诊或联系医生。"
            elif risk_level == "MEDIUM":
                final_response = "根据您描述的情况，建议您尽快联系主治医生。"
            else:
                final_response = "感谢您的咨询。如有更多问题，随时可以联系我们。"

    # 构建 AIMessage
    additional_kwargs: Dict[str, Any] = {}

    # 添加视频信息（如果存在）
    if video_url:
        additional_kwargs["video_url"] = video_url
    if video_password:
        additional_kwargs["video_password"] = video_password

    # Debug 模式添加分诊结果
    if debug_mode:
        # 过滤掉空值的槽位，保留完整槽位数据（包括 debug_info）
        collected_slots = {
            k: v for k, v in current_slots.items() if v.get("value")
        }

        additional_kwargs["triage_result"] = {
            "risk_level": risk_level,
            "care_plan_id": care_plan_id,
            "slots": collected_slots,
        }

    # 构建消息
    msg_kwargs: Dict[str, Any] = {"content": final_response}
    if additional_kwargs:
        msg_kwargs["additional_kwargs"] = additional_kwargs

    if logger:
        logger.info(f"📤 生成最终响应: risk_level={risk_level}, care_plan_id={care_plan_id}")

    return {
        "messages": [AIMessage(**msg_kwargs)],
        "risk_level": risk_level,
        "care_plan_id": care_plan_id,
        "triage_complete": True,
    }
