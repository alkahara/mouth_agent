"""
BaseOperator - Operator 抽象基类

所有 Operator（执行层）都应继承此基类。
Operator 负责执行 Manager 分配的具体任务。
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional

from langchain_core.messages import AIMessage


class BaseOperator(ABC):
    """
    Operator 抽象基类

    所有具体 Operator（AskSlotOperator, RAGOperator 等）必须实现此接口。
    """

    @property
    @abstractmethod
    def operator_id(self) -> str:
        """
        Operator 唯一标识

        Returns:
            str: Operator ID，如 "ask_slot", "rag_query"
        """
        pass

    @property
    @abstractmethod
    def operator_name(self) -> str:
        """
        Operator 显示名称

        Returns:
            str: Operator 名称
        """
        pass

    @abstractmethod
    async def execute(
        self,
        params: Dict[str, Any],
        state: Dict[str, Any],
        context: Any,
    ) -> Dict[str, Any]:
        """
        执行操作

        Args:
            params: Manager 分配的任务参数
            state: 当前图状态
            context: 运行时上下文（包含 LLM、logger 等）

        Returns:
            Dict: 状态更新（将合并到图状态）
        """
        pass

    def get_prompt_path(self) -> Optional[Path]:
        """
        获取该 Operator 使用的 Prompt 文件路径

        子类可覆盖此方法提供定制化 prompt。

        Returns:
            Optional[Path]: prompt 文件路径，或 None 使用内置模板
        """
        return None

    def _create_ai_message(
        self,
        content: str,
        additional_kwargs: Optional[Dict[str, Any]] = None,
    ) -> AIMessage:
        """
        创建 AIMessage

        Args:
            content: 消息内容
            additional_kwargs: 附加参数（如 options、triage_result 等）

        Returns:
            AIMessage: AI 消息对象
        """
        kwargs: Dict[str, Any] = {"content": content}
        if additional_kwargs:
            kwargs["additional_kwargs"] = additional_kwargs
        return AIMessage(**kwargs)


class OperatorResult:
    """
    Operator 执行结果

    封装 Operator 执行后的返回数据。
    """

    def __init__(
        self,
        messages: Optional[list] = None,
        slot_updates: Optional[Dict[str, Any]] = None,
        action: Optional[str] = None,
        action_params: Optional[Dict[str, Any]] = None,
        risk_level: Optional[str] = None,
        care_plan_id: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ):
        self.messages = messages or []
        self.slot_updates = slot_updates or {}
        self.action = action
        self.action_params = action_params or {}
        self.risk_level = risk_level
        self.care_plan_id = care_plan_id
        self.extra = extra or {}

    def to_state_update(self) -> Dict[str, Any]:
        """
        转换为图状态更新格式

        Returns:
            Dict: 状态更新字典
        """
        update: Dict[str, Any] = {}

        if self.messages:
            update["messages"] = self.messages
        if self.slot_updates:
            # 合并槽位更新到 slots 字段
            update["slot_updates"] = self.slot_updates
        if self.action:
            update["action"] = self.action
        if self.action_params:
            update["action_params"] = self.action_params
        if self.risk_level:
            update["risk_level"] = self.risk_level
        if self.care_plan_id:
            update["care_plan_id"] = self.care_plan_id

        # 合并额外字段
        update.update(self.extra)

        return update
