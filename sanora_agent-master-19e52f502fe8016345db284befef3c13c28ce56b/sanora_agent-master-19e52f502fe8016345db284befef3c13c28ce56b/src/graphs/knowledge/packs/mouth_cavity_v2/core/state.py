"""
State Schema - 口腔分诊 V2 状态定义

使用 Manager-Operator 架构的新状态结构。
"""

from typing import Annotated, Any, Dict, List, Optional

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from typing_extensions import NotRequired, TypedDict


class MouthCavityV2State(TypedDict, total=False):
    """
    口腔分诊 V2 状态

    使用 Manager-Operator 架构的状态结构。
    """

    # ============================================================
    # 消息历史
    # ============================================================
    messages: Annotated[List[AnyMessage], add_messages]

    # ============================================================
    # 流程控制
    # ============================================================
    current_flow_id: NotRequired[str]  # 当前激活的流程 ID: "bleeding" | "infection" | ...
    flow_initialized: NotRequired[bool]  # 流程是否已初始化

    # ============================================================
    # 槽位信息 (由 Manager 维护)
    # ============================================================
    # 格式: {slot_name: {"value": ..., "raw": ..., "confidence": ...}}
    slots: NotRequired[Dict[str, Dict[str, Any]]]
    pending_slot: NotRequired[str]  # 当前等待收集的槽位 ID

    # ============================================================
    # Manager 决策
    # ============================================================
    action: NotRequired[str]  # ask_slot | rag_query | assess_risk | final_response | fallback
    action_params: NotRequired[Dict[str, Any]]  # Manager 分配的任务参数
    manager_thought: NotRequired[str]  # Manager 的思考过程（用于调试）

    # ============================================================
    # 患者情绪与人文关怀
    # ============================================================
    patient_emotion: NotRequired[str]  # anxious | calm | urgent
    humanistic_care_delivered: NotRequired[List[str]]  # 已发送的关怀类型

    # ============================================================
    # 分诊结果
    # ============================================================
    risk_level: NotRequired[str]  # NONE | LOW | MEDIUM | HIGH
    care_plan_id: NotRequired[str]  # 护理方案 ID
    triage_complete: NotRequired[bool]  # 分诊是否完成

    # ============================================================
    # 意图路由
    # ============================================================
    intent_type: NotRequired[str]  # flow_related | general_query | flow_switch
    intent_subtype: NotRequired[str]  # self_intro | capabilities | greeting | other

    # ============================================================
    # 紧急情况
    # ============================================================
    is_emergency: NotRequired[bool]  # 是否触发紧急情况
    emergency_type: NotRequired[str]  # 紧急情况类型

    # ============================================================
    # 调试信息
    # ============================================================
    debug_mode: NotRequired[bool]  # 是否开启调试模式
    operator_log: NotRequired[str]  # Operator 执行日志


def create_initial_state() -> MouthCavityV2State:
    """
    创建初始状态

    Returns:
        MouthCavityV2State: 初始化的状态
    """
    return MouthCavityV2State(
        messages=[],
        current_flow_id="",
        flow_initialized=False,
        slots={},
        pending_slot="",
        action="",
        action_params={},
        manager_thought="",
        patient_emotion="calm",
        humanistic_care_delivered=[],
        risk_level="",
        care_plan_id="",
        triage_complete=False,
        is_emergency=False,
        emergency_type="",
        debug_mode=False,
        operator_log="",
    )


def merge_slots(
    current_slots: Dict[str, Dict[str, Any]],
    new_slots: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """
    合并槽位更新

    Args:
        current_slots: 当前槽位
        new_slots: 新槽位更新

    Returns:
        Dict: 合并后的槽位
    """
    result = current_slots.copy()
    for slot_name, slot_data in new_slots.items():
        if slot_name in result:
            # 合并，新值覆盖旧值
            result[slot_name] = {**result[slot_name], **slot_data}
        else:
            result[slot_name] = slot_data
    return result
