"""
决策树 - 硬编码槽位收集流程

根据已收集槽位确定下一步操作，参考口腔出血决策树图片。
"""

from typing import Any, Dict, Optional, Tuple

from src.models import RiskLevel


def decide_next_step(
    slots: Dict[str, Dict[str, Any]],
    debug_mode: bool = False,
) -> Dict[str, Any]:
    """
    决策树：确定下一步要问的槽位或返回最终结果

    Args:
        slots: 已收集的槽位 {"slot_name": {"value": ..., "raw": ...}}
        debug_mode: 是否为调试模式

    Returns:
        Dict: {
            "action": "ask_slot" | "respond",
            "slot_id": str (当 action=ask_slot),
            "risk_level": RiskLevel (当 action=respond),
            "care_plan_id": str (当 action=respond),
            "prompt_hint": str,
        }
    """

    def get_slot_value(slot_name: str) -> Optional[str]:
        """获取槽位值"""
        slot_data = slots.get(slot_name)
        if slot_data:
            return slot_data.get("value")
        return None

    def has_slot(slot_name: str) -> bool:
        """检查槽位是否已收集（任何非空值都算已收集）"""
        value = get_slot_value(slot_name)
        return value is not None and value != ""

    # ================================================================
    # 步骤 0: 询问是否为手术区域 (is_surgical_area)
    # 仅用于信息收集，不影响决策逻辑
    # ================================================================
    if not has_slot("is_surgical_area"):
        return {
            "action": "ask_slot",
            "slot_id": "is_surgical_area",
            "care_context": "greeting",  # 第一个问题带问候语
        }

    # ================================================================
    # 步骤 1: 询问诱因 (cause_trigger)
    # "没有"/"none" 也是有效回答
    # ================================================================
    if not has_slot("cause_trigger"):
        return {
            "action": "ask_slot",
            "slot_id": "cause_trigger",
        }

    # ================================================================
    # 步骤 2: 询问术后时间 (latest_time)
    # ================================================================
    if not has_slot("latest_time"):
        return {
            "action": "ask_slot",
            "slot_id": "latest_time",
        }

    stage = get_slot_value("latest_time")

    # ================================================================
    # 步骤 3: 术后 >5天 分支
    # ================================================================
    if stage == "late":
        if not has_slot("symptom_description"):
            return {
                "action": "ask_slot",
                "slot_id": "symptom_description",
            }
        symptom = get_slot_value("symptom_description")
        if symptom == "has_symptom":
            return {
                "action": "respond",
                "risk_level": RiskLevel.MEDIUM,
                "care_plan_id": "active_bleed_late",
                "prompt_hint": "术后超过五天伴有疼痛/发热等症状，考虑感染可能性大，需尽快就诊评估。",
            }
        # 无症状，直接指导压迫止血
        # 询问能否压迫止血
        can_compress = get_slot_value("can_compress")
        if not can_compress:
            return {
                "action": "ask_slot",
                "slot_id": "can_compress",
                "guidance_type": "compress_instructions",  # 先给压迫指导
            }

        # 无法压迫 → 高风险
        if can_compress == "cannot":
            return {
                "action": "respond",
                "risk_level": RiskLevel.HIGH,
                "care_plan_id": "cannot_press",
                "prompt_hint": "无法压迫止血，需尽快前往急诊。",
            }

        # 已尝试压迫但仍在出血
        if can_compress == "tried_but_bleeding":
            return {
                "action": "respond",
                "risk_level": RiskLevel.MEDIUM,
                "care_plan_id": "active_bleed_late",
                "prompt_hint": "术后晚期持续出血，建议尽快就医处理。",
            }

        # 没有纱布
        if can_compress == "no_gauze":
            return {
                "action": "ask_slot",
                "slot_id": "can_compress",  # 重新询问
                "guidance_type": "gauze_alternative",  # 提供替代品建议
            }

        # 可以压迫 → 询问压迫后结果
        if can_compress == "can":
            rebleed = get_slot_value("rebleed_after_compression")
            if not rebleed:
                return {
                    "action": "ask_slot",
                    "slot_id": "rebleed_after_compression",
                }

            # 压迫后不再出血 → 低风险
            if rebleed == "resolved":
                return {
                    "action": "respond",
                    "risk_level": RiskLevel.LOW,
                    "care_plan_id": "active_bleed_standard",
                    "prompt_hint": "压迫止血后仍需继续观察并避免诱因。",
                }

            # 压迫后再次出血 → 中风险
            if rebleed == "again":
                return {
                    "action": "respond",
                    "risk_level": RiskLevel.MEDIUM,
                    "care_plan_id": "active_bleed_late",
                    "prompt_hint": "术后晚期压迫后仍反复出血，需尽快就医。",
                }

    # ================================================================
    # 步骤 4: 术后 ≤5天，询问手术类型 (surgery_type)
    # ================================================================
    if not has_slot("surgery_type"):
        return {
            "action": "ask_slot",
            "slot_id": "surgery_type",
        }

    surgery_type = get_slot_value("surgery_type")

    # ================================================================
    # 步骤 5: 询问出血严重程度 (bleeding_severity)
    # ================================================================
    if not has_slot("bleeding_severity"):
        return {
            "action": "ask_slot",
            "slot_id": "bleeding_severity",
        }

    bleeding_severity = get_slot_value("bleeding_severity")

    # ================================================================
    # 特殊情况：口底血肿 → 高风险
    # ================================================================
    if bleeding_severity == "floor":
        return {
            "action": "respond",
            "risk_level": RiskLevel.HIGH,
            "care_plan_id": "floor_hematoma_emergency",
            "prompt_hint": "口底血肿威胁气道，需立即就医，必要时急救。",
        }

    # ================================================================
    # 轻微渗血分支
    # ================================================================
    if bleeding_severity == "minor":
        if stage == "early":
            return {
                "action": "respond",
                "risk_level": RiskLevel.NONE,
                "care_plan_id": "mild_oze_early",
                "prompt_hint": "术后轻微渗血是正常现象，无需压迫止血。",
            }
        else:
            return {
                "action": "respond",
                "risk_level": RiskLevel.LOW,
                "care_plan_id": "mild_oze_rebleed",
                "prompt_hint": "再次渗血多由诱因触发，纠正行为并观察。",
            }

    # ================================================================
    # 活动性出血分支
    # ================================================================
    if bleeding_severity == "active":
        # 询问是否可以压迫止血
        can_compress = get_slot_value("can_compress")
        if not can_compress:
            return {
                "action": "ask_slot",
                "slot_id": "can_compress",
                "guidance_type": "compress_instructions",  # 先给压迫指导
            }

        # 无法压迫 → 高风险
        if can_compress == "cannot":
            return {
                "action": "respond",
                "risk_level": RiskLevel.HIGH,
                "care_plan_id": "cannot_press",
                "prompt_hint": "无法压迫止血，需尽快前往急诊。",
            }

        # 已尝试压迫但仍在出血
        if can_compress == "tried_but_bleeding":
            is_vascular = surgery_type == "vascular"
            risk = RiskLevel.MEDIUM if is_vascular else RiskLevel.LOW
            return {
                "action": "respond",
                "risk_level": risk,
                "care_plan_id": "active_bleed_standard",
                "prompt_hint": "您已尝试压迫止血但仍持续出血，建议尽快就医处理。",
            }

        # 没有纱布
        if can_compress == "no_gauze":
            return {
                "action": "ask_slot",
                "slot_id": "can_compress",  # 重新询问
                "guidance_type": "gauze_alternative",  # 提供替代品建议
            }

        # 可以压迫 → 询问压迫后结果
        if can_compress == "can":
            rebleed = get_slot_value("rebleed_after_compression")
            if not rebleed:
                return {
                    "action": "ask_slot",
                    "slot_id": "rebleed_after_compression",
                }

            # 压迫后不再出血 → 低风险
            if rebleed == "resolved":
                return {
                    "action": "respond",
                    "risk_level": RiskLevel.LOW,
                    "care_plan_id": "active_bleed_early" if stage == "early" else "active_bleed_standard",
                    "prompt_hint": "压迫止血后仍需继续观察并避免诱因。",
                }

            # 压迫后再次出血 → 中风险
            if rebleed == "again":
                is_vascular = surgery_type == "vascular"
                risk = RiskLevel.MEDIUM if (stage == "late" or is_vascular) else RiskLevel.LOW
                return {
                    "action": "respond",
                    "risk_level": risk,
                    "care_plan_id": "active_bleed_standard",
                    "prompt_hint": "压迫后仍反复出血，需尽快就医。",
                }

    # ================================================================
    # 兜底：默认中风险
    # ================================================================
    return {
        "action": "respond",
        "risk_level": RiskLevel.MEDIUM,
        "care_plan_id": "active_bleed_standard",
        "prompt_hint": "根据您的情况，建议尽快联系医生获取专业指导。",
    }


def get_required_slots_for_stage(stage: Optional[str]) -> list:
    """
    根据当前阶段返回需要收集的槽位列表

    用于调试和进度显示。
    """
    base_slots = ["cause_trigger", "latest_time"]

    if stage == "late":
        return base_slots + ["symptom_description"]

    return base_slots + ["surgery_type", "bleeding_severity"]
