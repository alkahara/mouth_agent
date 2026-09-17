"""
BleedingFlow - 术后出血分诊流程

从现有 mouth_cavity_v2_graph.py 迁移的出血处理流程。
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..core import BaseFlow, FlowRegistry, SlotDefinition
from src.models import RiskLevel


@FlowRegistry.register("bleeding")
class BleedingFlow(BaseFlow):
    """
    术后出血分诊流程

    包含槽位定义、风险评估和护理方案。
    """

    # 出血严重程度选项（带图片）
    BLEEDING_OPTION_IMAGES = [
        {
            "key": "A",
            "label": "轻微渗血",
            "image_url": "https://sanora.oss-cn-beijing.aliyuncs.com/resources/light_bleed_30k.jpg",
        },
        {
            "key": "B",
            "label": "伤口持续鲜红出血",
            "image_url": "https://sanora.oss-cn-beijing.aliyuncs.com/resources/move_bleed.jpg",
        },
        {
            "key": "C",
            "label": "其他表现",
            "input_type": "text",
            "placeholder": "请详细描述您的出血情况（如：出血量、颜色、持续时间等）",
        },
    ]

    # 手术类型选项
    SURGERY_TYPE_OPTIONS = [
        {"key": "A", "label": "II期手术"},
        {"key": "B", "label": "上颌窦外提升植骨术"},
        {"key": "C", "label": "上颌窦内提升植骨术"},
        {"key": "D", "label": "软组织移植术"},
        {"key": "E", "label": "上颌前牙种植"},
        {"key": "F", "label": "上颌后牙种植"},
        {"key": "G", "label": "下颌前牙种植"},
        {"key": "H", "label": "下颌后牙种植"},
        {"key": "I", "label": "拔牙即刻种植术"},
        {"key": "J", "label": "位点保存术"},
        {"key": "K", "label": "块状骨移植术"},
        {"key": "L", "label": "骨柱植骨术"},
        {"key": "M", "label": "引导骨再生技术"},
        {"key": "N", "label": "上颌无牙颌种植术"},
        {"key": "O", "label": "下颌无牙颌种植术"},
        {"key": "P", "label": "种植体取出术"},
        {"key": "Q", "label": "牙齿拔除术"},
    ]

    # 出血部位选项
    BLEEDING_LOCATION_OPTIONS = [
        {"key": "A", "label": "舌侧（舌头下方、舌底）"},
        {"key": "B", "label": "腭侧（上颚、上方）"},
    ]

    # 手术区域选项（二选一）
    SURGICAL_AREA_OPTIONS = [
        {"key": "A", "label": "是"},
        {"key": "B", "label": "否"},
    ]

    # 涉及血管的高风险手术
    # B=上颌窦外提升植骨术, C=上颌窦内提升植骨术, D=软组织移植术,
    # K=块状骨移植术, L=骨柱植骨术, M=引导骨再生技术,
    # N=上颌无牙颌种植术, O=下颌无牙颌种植术
    VASCULAR_SURGERY_KEYS = {"B", "C", "D", "K", "L", "M", "N", "O"}

    @property
    def flow_id(self) -> str:
        return "bleeding"

    @property
    def flow_name(self) -> str:
        return "术后出血"

    @property
    def trigger_keywords(self) -> List[str]:
        return [
            "出血", "流血", "血", "渗血", "鲜红",
            "血块", "止血", "纱布", "压迫",
        ]

    @property
    def slots(self) -> List[SlotDefinition]:
        return [
            SlotDefinition(
                name="is_surgical_area",
                description="出血部位是否为手术区域",
                question_template="请问出血部位是否为手术区域？",
                options=self.SURGICAL_AREA_OPTIONS,
                order=0,  # 设置为 0，确保它是第一个问题
            ),
            SlotDefinition(
                name="cause_trigger",
                description="出血诱因",
                question_template="近期是否有咬硬物、漱口过猛、缝线松动、佩戴义齿/保持器或服用抗凝药等诱因？如果有，请描述具体情况。",
                order=1,
            ),
            SlotDefinition(
                name="latest_time",
                description="术后时间",
                question_template="请问出血发生在术后多久？（例如：手术后12小时/3天/一周）",
                parse_keywords={
                    "12小时": "early",
                    "24小时": "early",
                    "一天": "early",
                    "两天": "rebleed",
                    "2天": "rebleed",
                    "三天": "rebleed",
                    "3天": "rebleed",
                    "四天": "rebleed",
                    "4天": "rebleed",
                    "五天": "rebleed",
                    "5天": "rebleed",
                    "一周": "late",
                    "7天": "late",
                    "七天": "late",
                },
                order=2,
            ),
            SlotDefinition(
                name="symptom_description",
                description="伴随症状",
                question_template="是否伴随伤口疼痛、裂开，或出现发热、乏力、淋巴结肿大等全身症状？",
                condition="slots.get('latest_time', {}).get('value') == 'late'",
                order=3,
            ),
            SlotDefinition(
                name="surgery_type",
                description="手术类型",
                question_template="本次接受了什么手术或治疗？（可多选，最多4项）",
                options=self.SURGERY_TYPE_OPTIONS,
                multi_select=True,
                max_select=4,
                order=4,
            ),
            SlotDefinition(
                name="bleeding_severity",
                description="出血严重程度",
                question_template="当前出血表现更接近哪种情况？A. 轻微渗血；B. 伤口持续鲜红出血；C. 其他表现。",
                options=self.BLEEDING_OPTION_IMAGES,
                order=5,
            ),
            SlotDefinition(
                name="bleeding_location",
                description="出血部位",
                question_template="请问出血发生在哪个区域？",
                options=self.BLEEDING_LOCATION_OPTIONS,
                condition="slots.get('bleeding_severity', {}).get('value') in ['active', 'minor']",
                order=6,
            ),
            SlotDefinition(
                name="can_compress",
                description="是否可以压迫止血",
                question_template="当前部位是否能够使用干净纱布或棉卷进行压迫止血？",
                condition="slots.get('bleeding_severity', {}).get('value') == 'active'",
                order=7,
            ),
            SlotDefinition(
                name="rebleed_after_compression",
                description="压迫后是否再次出血",
                question_template="压迫止血后是否仍然持续或再次出血？",
                condition="slots.get('can_compress', {}).get('value') == 'can'",
                order=8,
            ),
        ]

    def assess_risk(self, slots: Dict[str, Any]) -> Tuple[RiskLevel, str]:
        """
        风险评估

        基于收集的槽位进行风险评估。
        """
        # 提取槽位值
        stage = slots.get("latest_time", {}).get("value", "")
        bleeding_severity = slots.get("bleeding_severity", {}).get("value", "")
        bleeding_location = slots.get("bleeding_location", {}).get("value", "")
        can_compress = slots.get("can_compress", {}).get("value", "")
        rebleed = slots.get("rebleed_after_compression", {}).get("value", "")
        symptom = slots.get("symptom_description", {}).get("value", "")
        surgery_type = slots.get("surgery_type", {}).get("value", "")

        # ================================================================
        # 紧急情况
        # ================================================================
        if bleeding_severity == "floor":
            return RiskLevel.HIGH, "floor_hematoma_emergency"

        # ================================================================
        # 术后晚期 + 有症状
        # ================================================================
        if stage == "late" and symptom == "has_symptom":
            return RiskLevel.MEDIUM, "active_bleed_late"

        # ================================================================
        # 轻微渗血
        # ================================================================
        if bleeding_severity == "minor":
            if stage == "early":
                return RiskLevel.NONE, "mild_oze_early"
            elif stage == "rebleed":
                return RiskLevel.LOW, "mild_oze_rebleed"
            else:
                return RiskLevel.MEDIUM, "mild_oze_rebleed"

        # ================================================================
        # 活动性出血
        # ================================================================
        if bleeding_severity == "active":
            # 无法压迫
            if can_compress == "cannot":
                if bleeding_location == "palatal":
                    return RiskLevel.HIGH, "palatal_cannot_compress"
                return RiskLevel.HIGH, "cannot_press"

            # 压迫后仍出血
            if rebleed == "again":
                is_vascular = self._is_vascular_surgery(surgery_type)
                if stage == "late":
                    return RiskLevel.MEDIUM, "active_bleed_late"
                elif is_vascular:
                    return RiskLevel.MEDIUM, "active_bleed_standard"
                else:
                    return RiskLevel.LOW, "active_bleed_standard"

            # 压迫后止住
            if rebleed == "resolved":
                is_vascular = self._is_vascular_surgery(surgery_type)
                if stage == "early":
                    return RiskLevel.LOW, "active_bleed_early"
                elif is_vascular:
                    return RiskLevel.MEDIUM, "active_bleed_standard"
                else:
                    return RiskLevel.LOW, "active_bleed_standard"

            # 可以压迫，尚未确认结果
            if can_compress == "can":
                return RiskLevel.LOW, "active_bleed_standard"

        # 默认
        return RiskLevel.MEDIUM, "active_bleed_standard"

    def get_care_plan(self, care_plan_id: str, slots: Dict[str, Any]) -> Dict[str, Any]:
        """
        获取护理方案

        返回护理方案的内容和相关指导。
        """
        # 护理方案映射
        care_plans = {
            "floor_hematoma_emergency": {
                "content": (
                    "⚠️ **口底血肿紧急情况**\n\n"
                    "口底血肿威胁气道，需立即就医，必要时急救。\n\n"
                    "**请立即行动**：\n"
                    "- 舌根抬高或呼吸困难 → 立即到急诊\n"
                    "- 如呼吸受限或难以下地，保持侧卧、将血液吐出避免呛咳，并拨打 120"
                ),
                "includes": ["avoid_triggers"],
            },
            "mild_oze_early": {
                "content": (
                    "术后轻微渗血属常见现象，是术后正常表现，无需压迫止血。\n\n"
                    "**护理建议**：\n"
                    "• 2 小时内不进烫食，24 小时内不刷牙、不漱口\n"
                    "• 吞咽口水而非吐出，停止舔舐或吸吮伤口\n"
                    "• 暂缓硬质食物，保持口腔清洁但轻柔\n"
                    "• 24 小时内可配合冰敷以减轻渗血\n\n"
                    "若吞咽困难、渗血量明显增多或心理压力大，可建议联系医生复查。"
                ),
                "includes": ["avoid_triggers", "icepack_instructions"],
            },
            "mild_oze_rebleed": {
                "content": (
                    "再次渗血多由诱因触发，当前为轻微渗血，先纠正行为并观察，无需额外压迫。\n\n"
                    "**护理建议**：\n"
                    "• 2 小时内不进烫食，24 小时内不刷牙、不漱口\n"
                    "• 吞咽口水而非吐出，停止舔舐或吸吮伤口\n"
                    "• 过渡义齿/保持器若压迫创口，需经医生调改后再佩戴\n\n"
                    "若渗血增多或伴发热、疼痛，提示就诊。"
                ),
                "includes": ["avoid_triggers"],
            },
            "active_bleed_early": {
                "content": (
                    "持续鲜红色出血需立即压迫止血。\n\n"
                    "**压迫止血步骤**：\n"
                    "1. 打开纱布包装后，清洁双手或佩戴手套\n"
                    "2. 将纱布折叠成卷状，大小适应伤口尺寸\n"
                    "3. 确保纱布与伤口紧密贴合\n"
                    "4. 牙齿上下咬合后微微用力即可\n"
                    "5. 放在伤口处咬 40 分钟\n"
                    "6. 吐出纱布，观察出血情况\n\n"
                    "⚠️ 压迫 40 分钟仍不停或出现头晕，即刻就诊。"
                ),
                "includes": ["avoid_triggers", "compress_instructions"],
                "video_url": "https://sanora.oss-cn-beijing.aliyuncs.com/resources/kouqiang-xuanjiao-yapozhixue.mp4",
                "video_password": "123456",
            },
            "active_bleed_standard": {
                "content": (
                    "24 小时后活动性出血一般有诱因，去除诱因并进行压迫止血。\n\n"
                    "**压迫止血步骤**：\n"
                    "1. 清洁双手，准备干净纱布\n"
                    "2. 将纱布折叠成卷状放在伤口处\n"
                    "3. 咬合 40 分钟\n"
                    "4. 观察是否止血\n\n"
                    "⚠️ 若两轮压迫后仍出血，建议尽快就医。"
                ),
                "includes": ["avoid_triggers", "compress_instructions"],
                "video_url": "https://sanora.oss-cn-beijing.aliyuncs.com/resources/kouqiang-xuanjiao-yapozhixue.mp4",
                "video_password": "123456",
            },
            "active_bleed_late": {
                "content": (
                    "术后 5 天以上仍大量出血，多考虑感染或深部损伤，需就医评估。\n\n"
                    "**建议**：\n"
                    "• 立即避免所有诱因\n"
                    "• 尽快面诊，必要时直奔急诊\n"
                    "• 就诊时携带手术资料"
                ),
                "includes": ["avoid_triggers"],
            },
            "cannot_press": {
                "content": (
                    "我理解突发出血会让人紧张，请先深呼吸、保持坐/半躺位。\n\n"
                    "由于出血点可能位于较深位置或靠近重要血管，这不是您的问题。\n"
                    "勿用手指或尖锐物自行探查创口。\n\n"
                    "**建议**：\n"
                    "1. 若可行走：请家属陪同立即前往最近急诊\n"
                    "2. 若无法行走或出现头晕、呼吸困难：保持侧卧，将口内血液吐出防呛，并立刻拨打 120\n"
                    "3. 就诊时携带手术资料，说明无法压迫的原因"
                ),
                "includes": ["comfort_cannot_press", "avoid_triggers"],
            },
            "palatal_cannot_compress": {
                "content": (
                    "腭侧出血无法有效压迫，可能涉及深部血管或特殊解剖位置。\n\n"
                    "⚠️ **腭侧出血较为危险**，请立即前往急诊或拨打 120。\n\n"
                    "就诊时说明无法压迫的情况，方便医生快速判断并处理。"
                ),
                "includes": ["comfort_cannot_press", "avoid_triggers"],
            },
        }

        return care_plans.get(care_plan_id, {
            "content": "请根据实际情况联系医生获取专业指导。",
            "includes": [],
        })

    def _is_vascular_surgery(self, surgery_type: str) -> bool:
        """判断是否为涉及血管的高风险手术"""
        if not surgery_type:
            return False

        # 支持多选
        surgery_keys = surgery_type.upper().split()
        return bool(set(surgery_keys) & self.VASCULAR_SURGERY_KEYS)
