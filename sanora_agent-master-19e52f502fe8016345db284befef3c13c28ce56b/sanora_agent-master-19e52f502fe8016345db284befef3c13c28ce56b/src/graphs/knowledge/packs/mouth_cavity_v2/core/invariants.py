"""
AgentInvariants - Agent 宪法

第一层：框架层硬编码的不变量。
这些规则不依赖 LLM 推理，由代码强制执行。
"""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class EmergencyAction:
    """紧急情况处理动作"""
    action_type: str  # "immediate_emergency" | "urgent_referral"
    message: str
    call_120: bool = False


class AgentInvariants:
    """
    Agent 不变量 - 框架层强制执行

    这些规则在 LLM 处理之前检查，确保安全边界不被突破。
    """

    # 紧急情况触发词（绕过 LLM，直接触发）
    EMERGENCY_TRIGGERS: Dict[str, EmergencyAction] = {
        "口底血肿": EmergencyAction(
            action_type="immediate_emergency",
            message="检测到口底血肿症状，这可能危及气道安全！请立即前往急诊或拨打 120。",
            call_120=True,
        ),
        "口底肿胀": EmergencyAction(
            action_type="immediate_emergency",
            message="检测到口底肿胀症状，这可能危及气道安全！请立即前往急诊或拨打 120。",
            call_120=True,
        ),
        "呼吸困难": EmergencyAction(
            action_type="immediate_emergency",
            message="呼吸困难是紧急情况！请保持侧卧位，立即拨打 120 或前往最近急诊。",
            call_120=True,
        ),
        "气道阻塞": EmergencyAction(
            action_type="immediate_emergency",
            message="气道阻塞是危急情况！请立即拨打 120，保持侧卧位，等待救援。",
            call_120=True,
        ),
        "舌根抬高": EmergencyAction(
            action_type="immediate_emergency",
            message="舌根抬高提示可能有气道风险！请立即前往急诊或拨打 120。",
            call_120=True,
        ),
        "吞咽困难伴呼吸不畅": EmergencyAction(
            action_type="immediate_emergency",
            message="吞咽困难伴呼吸不畅需要紧急处理！请立即就医或拨打 120。",
            call_120=True,
        ),
    }

    # 需要立即转诊但不需要 120 的情况
    URGENT_REFERRAL_TRIGGERS: Dict[str, str] = {
        "持续大量出血": "您描述的情况需要尽快就医，请立即前往口腔急诊。",
        "血液溢满口腔": "大量出血需要专业处理，请尽快前往急诊。",
    }

    # V2 的 10 条不变量（文档化，部分在代码中执行）
    INVARIANTS: List[str] = [
        # 安全
        "1. 紧急情况（口底血肿/呼吸困难）框架层直接拦截，不过 LLM",
        "2. 不可逆动作（最终诊断）前必须二次确认",
        "3. 无法判断风险时，默认建议线下就诊",
        # 诚实
        "4. 不制造虚假确定性，判断用'可能''建议'",
        "5. 不隐藏关键假设，判断依据必须可追溯",
        "6. 不操纵用户情绪，提供事实让用户判断",
        # 判断
        "7. 成本-收益推理可观测，输出 reasoning 字段",
        "8. 不确定性有置信度，低于阈值必须追问",
        # 人文
        "9. 识别用户情绪状态，调整响应策略",
        "10. 尊重用户最终决策权，提供选项而非强制",
    ]

    @classmethod
    def check_emergency(cls, user_message: str) -> Optional[EmergencyAction]:
        """
        检查用户消息是否触发紧急情况

        在 LLM 处理之前调用，确保紧急情况立即被识别。

        Args:
            user_message: 用户消息

        Returns:
            Optional[EmergencyAction]: 紧急情况动作，或 None
        """
        message_lower = user_message.lower()

        for keyword, action in cls.EMERGENCY_TRIGGERS.items():
            if keyword in message_lower:
                return action

        return None

    @classmethod
    def check_urgent_referral(cls, user_message: str) -> Optional[str]:
        """
        检查用户消息是否需要紧急转诊

        Args:
            user_message: 用户消息

        Returns:
            Optional[str]: 转诊提示消息，或 None
        """
        message_lower = user_message.lower()

        for keyword, message in cls.URGENT_REFERRAL_TRIGGERS.items():
            if keyword in message_lower:
                return message

        return None

    @classmethod
    def get_emergency_response(cls, action: EmergencyAction) -> Dict:
        """
        生成紧急情况响应

        Args:
            action: 紧急情况动作

        Returns:
            Dict: 响应数据
        """
        response = {
            "action": "emergency",
            "action_type": action.action_type,
            "message": action.message,
            "risk_level": "HIGH",
            "triage_complete": True,
        }

        if action.call_120:
            response["call_120"] = True
            response["message"] += "\n\n🚨 请立即拨打 120！"

        return response

    @classmethod
    def validate_final_response(cls, response: Dict) -> Dict:
        """
        验证最终响应是否符合不变量

        确保输出符合诚实、人文等原则。

        Args:
            response: 待验证的响应

        Returns:
            Dict: 验证/修正后的响应
        """
        # 确保高风险情况有明确就医建议
        if response.get("risk_level") == "HIGH":
            message = response.get("message", "")
            if "就医" not in message and "急诊" not in message and "120" not in message:
                response["message"] = message + "\n\n⚠️ 建议您尽快就医或前往急诊。"

        return response
