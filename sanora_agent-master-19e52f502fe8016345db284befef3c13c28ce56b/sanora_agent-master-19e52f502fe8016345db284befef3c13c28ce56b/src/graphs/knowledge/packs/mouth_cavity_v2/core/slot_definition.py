"""
SlotDefinition - 槽位定义数据类

定义收集患者信息所需的槽位结构，供 Manager 和 Operators 使用。
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SlotDefinition:
    """
    槽位定义

    Attributes:
        name: 槽位名称（唯一标识）
        description: 槽位描述，用于 Manager Prompt
        required: 是否必填
        options: 可选项列表，格式 [{"key": "A", "label": "选项A"}, ...]
        condition: 条件表达式，如 "slots.get('latest_time') == 'late'"
        question_template: 询问模板
        parse_keywords: 解析关键词映射，如 {"24小时内": "early", "一周": "late"}
        order: 槽位收集顺序（可选）
        multi_select: 是否支持多选
        max_select: 最大选择数量
    """

    name: str
    description: str
    required: bool = True
    options: Optional[List[Dict[str, Any]]] = None
    condition: Optional[str] = None
    question_template: str = ""
    parse_keywords: Optional[Dict[str, str]] = None
    order: int = 0
    multi_select: bool = False
    max_select: int = 1

    def should_ask(self, current_slots: Dict[str, Any]) -> bool:
        """
        判断是否应该询问该槽位

        Args:
            current_slots: 当前已收集的槽位值

        Returns:
            bool: 是否应该询问
        """
        # 如果已有值，不再询问
        if self.name in current_slots and current_slots[self.name].get("value"):
            return False

        # 如果有条件，评估条件
        if self.condition:
            try:
                # 安全地评估条件表达式
                # 只允许访问 slots 变量
                slots = current_slots
                return eval(self.condition, {"__builtins__": {}}, {"slots": slots})
            except Exception:
                # 条件评估失败，默认询问
                return True

        return True

    def to_prompt_dict(self) -> Dict[str, Any]:
        """转换为 Prompt 使用的字典格式"""
        result = {
            "name": self.name,
            "description": self.description,
            "required": self.required,
            "question_template": self.question_template,
        }
        if self.options:
            result["options"] = self.options
        if self.condition:
            result["condition"] = self.condition
        return result


@dataclass
class SlotValue:
    """
    槽位值

    Attributes:
        value: 解析后的标准化值
        raw: 用户原始输入
        confidence: 置信度 (0.0 - 1.0)
        source: 来源 ("user" | "inferred")
    """

    value: Any
    raw: str = ""
    confidence: float = 1.0
    source: str = "user"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "value": self.value,
            "raw": self.raw,
            "confidence": self.confidence,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SlotValue":
        return cls(
            value=data.get("value"),
            raw=data.get("raw", ""),
            confidence=data.get("confidence", 1.0),
            source=data.get("source", "user"),
        )
