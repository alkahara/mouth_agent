"""
槽位解析器 - 从用户自然语言中提取标准化槽位值

复用 V1 的解析逻辑，确保用户输入（如"4天前"）能被正确解析为标准值（如"rebleed"）。
"""

import re
from typing import Any, Dict, List, Optional


def parse_latest_time(text: str) -> Optional[Dict[str, Any]]:
    """
    解析术后时间

    将用户的自然语言描述转换为标准分期：
    - "early": 术后 0-24 小时
    - "rebleed": 术后 1-5 天
    - "late": 术后 5 天以上

    Args:
        text: 用户输入的时间描述

    Returns:
        Dict: {"value": "early|rebleed|late", "raw": 原始文本}
    """
    if not text:
        return None

    normalized = text.strip().lower()
    normalized = (
        normalized.replace("大概", "")
        .replace("左右", "")
        .replace("约", "")
        .replace("大约", "")
        .replace("前", "")  # "4天前" -> "4天"
    )

    if not normalized:
        return None

    # 中文数字映射
    chinese_numbers = {
        "一": 1,
        "二": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
        "十": 10,
        "两": 2,
        "半": 0.5,
    }

    # 转换中文数字为阿拉伯数字
    for chinese, arabic in chinese_numbers.items():
        if chinese + "天" in normalized or chinese + "日" in normalized:
            normalized = normalized.replace(chinese + "天", str(int(arabic)) + "天")
            normalized = normalized.replace(chinese + "日", str(int(arabic)) + "日")

    # 关键词分类
    early_keywords = [
        "刚",
        "现在",
        "立刻",
        "当时",
        "今天",
        "不到一天",
        "半天",
        "刚做",
        "刚刚",
        "几个小时",
    ]
    rebleed_keywords = [
        "1天",
        "这两天",
        "两天",
        "2天",
        "三天",
        "3天",
        "四天",
        "4天",
        "五天",
        "5天",
        "24小时后",
        "第一天",
        "第二天",
        "第三天",
        "第四天",
        "第五天",
    ]
    late_keywords = [
        "六天",
        "6天",
        "七天",
        "7天",
        "八天",
        "8天",
        "九天",
        "9天",
        "十天",
        "10天",
        "一周",
        "超过五天",
        "半个月",
        "一个月",
        "第六天",
        "上周",
    ]

    # ================================================================
    # 优先使用数字提取进行判断（更精确）
    # ================================================================
    digits = _extract_digits(normalized)
    if digits:
        number = digits[0]
        if "小时" in normalized or "h" in normalized:
            hours = number
            if hours < 24:
                return {"value": "early", "raw": text}
            if hours <= 120:  # 5天 = 120小时
                return {"value": "rebleed", "raw": text}
            return {"value": "late", "raw": text}

        # 如果明确包含"天"或"日"，按天数判断
        if "天" in normalized or "日" in normalized:
            if number == 0:
                return {"value": "early", "raw": text}
            if 1 <= number <= 5:  # 1-5天（含5天）→ rebleed
                return {"value": "rebleed", "raw": text}
            if number > 5:  # >5天 → late
                return {"value": "late", "raw": text}

        # 如果包含"周"，按周计算
        if any(token in normalized for token in ["周", "星期", "礼拜"]):
            # 但如果同时有天数，优先用天数
            pass  # 继续往下走关键词匹配

    # ================================================================
    # 关键词匹配（作为兜底）
    # ================================================================
    if any(keyword in normalized for keyword in early_keywords):
        return {"value": "early", "raw": text}
    if any(keyword in normalized for keyword in late_keywords):
        return {"value": "late", "raw": text}
    if any(keyword in normalized for keyword in rebleed_keywords):
        return {"value": "rebleed", "raw": text}

    # 如果有数字但没有明确单位，尝试按天数判断
    if digits:
        number = digits[0]
        if number == 0:
            return {"value": "early", "raw": text}
        if 1 <= number <= 5:
            return {"value": "rebleed", "raw": text}
        if number > 5:
            return {"value": "late", "raw": text}

    if "不久" in normalized or "刚做完" in normalized:
        return {"value": "early", "raw": text}

    return None


def _extract_digits(text: str) -> List[int]:
    """从文本中提取数字"""
    matches = re.findall(r"\d+", text)
    return [int(m) for m in matches] if matches else []


def normalize_slot_value(slot_name: str, slot_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    规范化槽位值

    对特定槽位的用户原始输入进行后处理，确保值符合标准格式。

    Args:
        slot_name: 槽位名称
        slot_data: 槽位数据 {"value": ..., "raw": ..., "confidence": ...}

    Returns:
        Dict: 规范化后的槽位数据
    """
    if not slot_data:
        return slot_data

    # 获取原始值
    raw_value = slot_data.get("raw") or slot_data.get("value") or ""
    current_value = slot_data.get("value", "")

    # 根据槽位类型进行解析
    if slot_name == "latest_time":
        # 如果 value 已经是标准值，跳过
        if current_value in ("early", "rebleed", "late"):
            return slot_data

        # 尝试解析原始文本
        parsed = parse_latest_time(raw_value)
        if parsed:
            return {
                **slot_data,
                "value": parsed["value"],
                "raw": raw_value,
                "normalized": True,
            }

    elif slot_name == "bleeding_severity":
        # 出血严重程度映射：选项 key/label -> 标准值
        severity_mapping = {
            # 选项 key
            "A": "minor",
            "B": "active",
            "C": "other",
            # 选项 label
            "轻微渗血": "minor",
            "伤口持续鲜红出血": "active",
            "活动性出血": "active",
            "持续鲜红出血": "active",
            "鲜红出血": "active",
            "其他表现": "other",
            # 特殊情况
            "口底血肿": "floor",
            "舌下出血": "floor",
            "舌底血肿": "floor",
        }

        # 如果已经是标准值，直接返回
        if current_value in ("minor", "active", "floor", "other"):
            return slot_data

        # 确保 current_value 是字符串
        if not isinstance(current_value, str):
            current_value = str(current_value) if current_value else ""

        # 尝试直接匹配（包括中文和原始值）
        normalized_value = severity_mapping.get(current_value)

        # 如果没找到，尝试大写匹配（处理 A/B/C 选项）
        if not normalized_value:
            normalized_value = severity_mapping.get(current_value.upper())

        # 如果还没找到，尝试模糊匹配
        if not normalized_value:
            value_lower = current_value.lower()
            if "轻微" in value_lower or "渗血" in value_lower:
                normalized_value = "minor"
            elif "鲜红" in value_lower or "活动" in value_lower or "持续" in value_lower:
                normalized_value = "active"
            elif "口底" in value_lower or "舌下" in value_lower or "舌底" in value_lower:
                normalized_value = "floor"
            else:
                normalized_value = "other"

        return {
            **slot_data,
            "value": normalized_value,
            "raw": raw_value,
            "normalized": True,
        }

    elif slot_name == "surgery_type":
        # 涉血管手术类型
        # B=上颌窦外提升植骨术, C=上颌窦内提升植骨术, D=软组织移植术,
        # K=块状骨移植术, L=骨柱植骨术, M=引导骨再生技术,
        # N=上颌无牙颌种植术, O=下颌无牙颌种植术
        VASCULAR_SURGERY_KEYS = {"B", "C", "D", "K", "L", "M", "N", "O"}

        # 支持多种格式：
        # 1. 列表格式: ["K", "M", "Q"]
        # 2. 字符串格式: "B C" 或 "B,C" 或 "B"
        if isinstance(current_value, list):
            # LLM 返回的是列表
            surgery_keys = [str(k).upper() for k in current_value]
        elif isinstance(current_value, str):
            # 字符串格式，支持空格或逗号分隔
            surgery_keys = current_value.upper().replace(",", " ").split() if current_value else []
        else:
            surgery_keys = []

        is_vascular = bool(set(surgery_keys) & VASCULAR_SURGERY_KEYS)

        # 计算匹配的术式
        matched_vascular = [k for k in surgery_keys if k in VASCULAR_SURGERY_KEYS]
        matched_non_vascular = [k for k in surgery_keys if k not in VASCULAR_SURGERY_KEYS]

        # 构建 debug_info（与 V1 保持一致）
        debug_info = {
            "user_input": raw_value,
            "parsed_surgeries": surgery_keys,
            "matched_vascular": matched_vascular if matched_vascular else [],
            "matched_non_vascular": matched_non_vascular if matched_non_vascular else [],
            "final_judgment": "涉血管(vascular) → 走'是'的逻辑" if is_vascular else "非涉血管(non_vascular) → 走'否'的逻辑"
        }

        # 标准化 value 为字符串格式（用于后续决策树判断）
        # 如果包含涉血管术式，标记为 "vascular"；否则标记为选中的第一个术式
        normalized_surgery_value = "vascular" if is_vascular else (surgery_keys[0] if surgery_keys else "")

        return {
            **slot_data,
            "value": normalized_surgery_value,
            "raw": raw_value if isinstance(raw_value, str) else ",".join(surgery_keys),
            "surgery_keys": surgery_keys,  # 保留完整的术式列表
            "debug_info": debug_info,
            "normalized": True,
        }

    return slot_data


def normalize_all_slots(
    slot_updates: Dict[str, Dict[str, Any]]
) -> Dict[str, Dict[str, Any]]:
    """
    规范化所有槽位更新

    Args:
        slot_updates: Manager 输出的槽位更新

    Returns:
        Dict: 规范化后的槽位更新
    """
    if not slot_updates:
        return slot_updates

    normalized = {}
    for slot_name, slot_data in slot_updates.items():
        normalized[slot_name] = normalize_slot_value(slot_name, slot_data)

    return normalized
