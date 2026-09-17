"""
MouthCavityV2Behavior - V2 口腔分诊行为层

复用 V1 的 MouthCavityBehavior 逻辑，提供：
- 首次问候语
- 重置处理
- 预处理逻辑
"""

from __future__ import annotations

from typing import Optional, Tuple

from .base import GraphBehavior
from ...models import MessageRole

CARING_MESSAGE = (
    "亲爱的患者您好，我是北大口腔四门诊的种植牙术后患者管理智能AI助手，请问您有什么问题？"
)

NON_IMPLANT_MESSAGE = (
    "抱歉，您的问题已超出我的专业范围。如果您在牙齿种植术后出现异常情况，请及时联系您的主治医生或前往急诊科就诊。若其他问题，需由专业医护人员进行评估和处理。"
)

RESET_KEYWORDS = {"重新评估", "重新開始", "重新开始"}
BLEED_KEYWORDS = {
    "出血",
    "流血",
    "渗血",
    "血块",
    "血丝",
    "血流",
    "止不住血",
    "鲜血",
    "止血",
    "压迫",
    "纱布",
    "棉卷",
}
IMPLANT_KEYWORDS = {"种植", "植牙", "种牙", "种植牙", "植体"}

# 轻微症状关键词
MILD_SYMPTOM_KEYWORDS = {
    "口水粉色", "口水带血", "唾液粉红", "唾液带血", "口水粉红",
    "少量血丝", "一点点血", "一点血", "有点血",
    "纱布上有点血", "有点渗血", "一点渗血",
}

# 轻微症状快速应答
MILD_SYMPTOM_RESPONSE = (
    "您好，术后口水呈现粉红色或有少量血丝，是因为唾液混合了少量渗血，"
    "这在术后24小时内是正常现象。如果出血量没有明显增多或伴有其他不适，"
    "请不要过度担心，继续观察即可。\n\n"
    "建议：\n"
    "• 避免频繁吐口水或漱口\n"
    "• 避免用舌头舔舐伤口\n"
    "• 避免进食过硬或过烫的食物\n\n"
    "如果出血量明显增大、持续不止或伴有其他不适症状，请及时告知我。"
)

# 用户在流程中可能回答的关键词
DIALOGUE_KEYWORDS = {
    "是", "否", "有", "没有", "无", "能", "不能", "可以", "不可以",
    "舌侧", "腭侧", "上方", "下方", "轻微", "严重",
    "天", "小时", "拔牙", "手术",
}

# 问候语关键词
GREETING_KEYWORDS = {
    "你好", "您好", "hi", "hello", "嗨", "哈喽", "在吗", "在么", "在不在",
    "早上好", "上午好", "中午好", "下午好", "晚上好", "早",
}

# 身份询问关键词
IDENTITY_KEYWORDS = {
    "你是谁", "您是谁", "你是什么", "你是哪位", "介绍一下自己", "自我介绍",
    "你能做什么", "你有什么功能", "你会什么", "你的能力",
}

# 自我介绍消息（包含角色和能力）
SELF_INTRO_MESSAGE = (
    "您好！我是北大口腔四门诊的种植牙术后患者管理智能AI助手。\n\n"
    "我可以帮助您解决以下问题：\n"
    "• 种植牙术后出血的评估与处理建议\n"
    "• 术后常见症状的判断与指导\n"
    "• 术后注意事项的咨询\n\n"
    "如果您在种植牙术后遇到任何不适或疑问，请随时告诉我，我会尽力为您提供专业的建议。"
)


class MouthCavityV2Behavior(GraphBehavior):
    """V2 口腔分诊行为钩子"""

    def __init__(self) -> None:
        self._welcomed_threads: set[str] = set()
        self._confirmed_threads: set[str] = set()

    def preprocess(self, request, graph, app_config, thread_id: str):
        """
        预处理请求
        
        V2 所有的意图识别（问候、身份询问、病情咨询等）都由 Graph 内部的 Intent Router 处理。
        此处仅处理全局控制指令（如重置）。
        """
        _msg, text = self._last_user_message(request)
        if not text:
            return None

        if text in RESET_KEYWORDS:
            request.reset_state = True
            request.messages = []
            return None

        return None

    def should_reset(self, request, graph, app_config, thread_id: str) -> bool:
        if getattr(request, "reset_state", False):
            return True
        _msg, text = self._last_user_message(request)
        if text in RESET_KEYWORDS:
            request.reset_state = True
            request.messages = []
            return True
        return False

    def on_reset(self, request, graph, app_config, thread_id: str):
        self._welcomed_threads.discard(thread_id)
        self._confirmed_threads.discard(thread_id)
        request.messages = []
        return self.build_text_response(
            request,
            CARING_MESSAGE,
            app_config,
            thread_id=thread_id,
            record_welcome=True,
        )

    def initial_response(self, request, graph, app_config, thread_id: str):
        if thread_id in self._welcomed_threads:
            return None
        self._welcomed_threads.add(thread_id)
        request.messages = []
        return self.build_text_response(
            request,
            CARING_MESSAGE,
            app_config,
            thread_id=thread_id,
            record_welcome=True,
        )

    def on_state_cleared(self, thread_id: str) -> None:
        self._welcomed_threads.discard(thread_id)
        self._confirmed_threads.discard(thread_id)

    @staticmethod
    def _last_user_message(request) -> Tuple[Optional[object], str]:
        for message in reversed(request.messages or []):
            if message.role == MessageRole.USER:
                normalized = (message.content or "").strip().lower().replace(" ", "")
                return message, normalized
        return None, ""
