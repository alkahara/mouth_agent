"""
AskSlotOperator - 槽位询问 Operator

负责根据 Manager 的指令生成槽位询问问题。
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.runtime import Runtime

from ..core import BaseFlow, FlowRegistry, MouthCavityV2State, SlotDefinition


# Prompt 文件路径
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def _load_prompt(filename: str, flow: Optional[BaseFlow] = None) -> str:
    """
    加载 Prompt 文件

    优先使用 Flow 提供的定制 Prompt，否则使用默认 Prompt。
    """
    # 检查 Flow 是否提供定制 Prompt
    if flow:
        custom_path = flow.get_ask_slot_prompt_path()
        if custom_path and custom_path.exists():
            return custom_path.read_text(encoding="utf-8")

    # 使用默认 Prompt
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


def ask_slot_operator(
    state: MouthCavityV2State,
    runtime: Runtime,
) -> Dict[str, Any]:
    """
    槽位询问 Operator

    根据 Manager 的 action_params 生成槽位询问问题。

    Args:
        state: 当前状态
        runtime: 运行时上下文

    Returns:
        Dict: 状态更新（包含 AIMessage）
    """
    import random

    logger = getattr(runtime.context, "logger", None)

    if logger:
        logger.info("📝 AskSlot Operator 开始")

    action_params = state.get("action_params", {})
    current_flow_id = state.get("current_flow_id", "")
    current_slots = state.get("slots", {})
    patient_emotion = state.get("patient_emotion", "calm")
    debug_mode = state.get("debug_mode", False)
    flow_initialized = state.get("flow_initialized", False)
    humanistic_care_delivered = state.get("humanistic_care_delivered", [])

    # 获取槽位信息
    slot_id = action_params.get("slot_id", "")
    guidance_type = action_params.get("guidance_type", "")

    # 获取流程实例
    flow = FlowRegistry.get_or_none(current_flow_id)

    # ================================================================
    # 压迫止血指导（在询问 can_compress 之前显示）
    # ================================================================
    COMPRESS_INSTRUCTIONS = """压迫止血：打开纱布包装后，清洁双手或佩戴手套，将纱布折叠成卷状，大小适应伤口尺寸，确保纱布与伤口紧密贴合，压迫止血时应避免过度用力，牙齿上下咬合后微微用力即可，以免损伤周围组织，放在伤口处咬40分钟后，吐出纱布，观察伤口出血情况，一般可自行停止。密码：123456。若不能改善，需及时就诊。"""

    GAUZE_ALTERNATIVE = """若家中无纱布时，可选择干净、柔软、吸水性好的棉质物品替代，如干净的毛巾、洗脸巾、手帕等。注意不要选择粗糙的卫生纸（含荧光剂/添加剂）、松散的棉花（易留纤维），这些可能刺激伤口或残留纤维。"""

    # ================================================================
    # 获取问题模板（优先使用槽位定义的模板，而非 Manager 生成的问题）
    # ================================================================
    slot_def = None
    if flow:
        for s in flow.slots:
            if s.name == slot_id:
                slot_def = s
                break

    if slot_def:
        final_question = slot_def.question_template
    else:
        final_question = action_params.get("question", f"请提供 {slot_id} 的信息。")

    # ================================================================
    # 首次介绍逻辑（仅在流程刚初始化时添加问候语）
    # ================================================================
    greeting_message = ""
    if not flow_initialized or len(current_slots) == 0:
        # 问候语列表（与 V1 一致）
        greetings = [
            "我理解突然出血会让您感到紧张，请先深呼吸、保持冷静，我会一步步指导您处理。",
            "别担心，出血情况是可以控制的，请先保持镇定，我来帮助您。",
            "您及时联系我们是正确的选择，请放心，我会帮助您评估情况并指导处理。",
        ]
        # 过滤已使用的问候语
        available_greetings = [g for g in greetings if g not in humanistic_care_delivered]
        if available_greetings:
            greeting_message = random.choice(available_greetings)
            humanistic_care_delivered.append(greeting_message)

    # ================================================================
    # 根据患者情绪添加关怀语
    # ================================================================
    care_message = ""
    if patient_emotion == "anxious" and greeting_message == "":
        care_phrases = [
            "我知道看到出血会让人不安，但请保持镇定，我们会一步步指导您处理。",
            "请保持冷静，正确的处理方式可以有效控制出血。",
        ]
        available_care = [c for c in care_phrases if c not in humanistic_care_delivered]
        if available_care:
            care_message = random.choice(available_care)
            humanistic_care_delivered.append(care_message)

    # ================================================================
    # 组合最终消息
    # ================================================================
    message_parts = []
    if greeting_message:
        message_parts.append(greeting_message)
    if care_message:
        message_parts.append(care_message)

    # 如果是询问 can_compress，先提供压迫止血指导
    if slot_id == "can_compress":
        if guidance_type == "gauze_alternative":
            message_parts.append(GAUZE_ALTERNATIVE)
        else:
            message_parts.append(COMPRESS_INSTRUCTIONS)
        # 修改问题，加上"了解步骤后"
        final_question = "了解步骤后，当前部位是否能够使用干净纱布或棉卷进行压迫止血？"

    message_parts.append(final_question)

    final_message = "\n\n".join(message_parts)

    # 构建 AIMessage
    additional_kwargs: Dict[str, Any] = {}

    # 如果是询问 can_compress 且提供了压迫止血步骤，添加视频信息
    if slot_id == "can_compress" and guidance_type != "gauze_alternative":
        additional_kwargs["video_url"] = "https://sanora.oss-cn-beijing.aliyuncs.com/resources/kouqiang-xuanjiao-yapozhixue.mp4"
        additional_kwargs["video_password"] = "123456"

    # 添加选项（如果有）
    if slot_def and slot_def.options:
        additional_kwargs["options"] = slot_def.options

    # 添加多选配置（如果有）
    if slot_def and slot_def.multi_select:
        additional_kwargs["multi_select"] = True
        additional_kwargs["max_select"] = slot_def.max_select
        additional_kwargs["confirm_button_text"] = "确认选择"

    # Debug 模式添加调试信息
    if debug_mode:
        additional_kwargs["debug_info"] = {
            "operator": "ask_slot",
            "slot_id": slot_id,
            "patient_emotion": patient_emotion,
        }

    # 构建消息
    msg_kwargs: Dict[str, Any] = {"content": final_message}
    if additional_kwargs:
        msg_kwargs["additional_kwargs"] = additional_kwargs

    if logger:
        logger.info(f"📤 生成问题: {final_message[:100]}...")

    return {
        "messages": [AIMessage(**msg_kwargs)],
        "pending_slot": slot_id,
        "flow_initialized": True,
        "humanistic_care_delivered": humanistic_care_delivered,
    }

