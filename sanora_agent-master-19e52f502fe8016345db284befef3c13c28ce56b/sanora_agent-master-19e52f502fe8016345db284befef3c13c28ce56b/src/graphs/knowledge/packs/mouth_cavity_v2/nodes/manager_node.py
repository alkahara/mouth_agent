"""
Manager Node - 决策管理节点

Manager 是口腔分诊 V2 的决策大脑，负责：
1. 理解用户意图
2. 提取槽位信息
3. 决定下一步操作（分配给哪个 Operator）
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage
from langgraph.runtime import Runtime
from pydantic import BaseModel, Field

from ..core import (
    AgentInvariants,
    BaseFlow,
    FlowRegistry,
    MouthCavityV2State,
    SlotDefinition,
    merge_slots,
    normalize_all_slots,
    decide_next_step,
)



# ================================================================
# Pydantic Model 定义（用于 LLM 结构化输出）
# ================================================================

class SlotUpdate(BaseModel):
    """单个槽位的更新信息"""

    value: str = Field(
        default="",
        description="标准化的槽位值",
    )
    raw: str = Field(
        default="",
        description="用户原始回答",
    )
    confidence: float = Field(
        default=0.9,
        description="提取结果的置信度 (0.0-1.0)",
    )


class ManagerResult(BaseModel):
    """Manager 槽位解析结果模型"""

    slot_updates: Dict[str, SlotUpdate] = Field(
        default_factory=dict,
        description="槽位更新字典，key 为槽位名，value 为更新详情",
    )
    patient_emotion: str = Field(
        default="calm",
        description="患者情绪: calm=平静, anxious=焦虑, urgent=紧急",
    )
    slot_valid: bool = Field(
        default=True,
        description="用户回答是否针对当前待收集槽位（true=有效回答, false=完全不相关）",
    )
    reasoning: str = Field(
        default="",
        description="简要说明解析逻辑",
    )


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


def _is_network_error(exc: Exception) -> bool:
    """
    判断异常是否为网络连接错误

    检测常见的网络类异常：
    - openai.APIConnectionError
    - httpx.ConnectError / httpcore.ConnectError
    - ConnectionRefusedError / ConnectionError
    - TimeoutError / asyncio.TimeoutError
    """
    exc_type_name = type(exc).__name__
    network_error_types = (
        "APIConnectionError",
        "ConnectError",
        "ConnectionError",
        "ConnectionRefusedError",
        "TimeoutError",
        "ReadTimeout",
        "ConnectTimeout",
    )
    if exc_type_name in network_error_types:
        return True

    # 检查异常链（__cause__）
    cause = getattr(exc, "__cause__", None)
    if cause and type(cause).__name__ in network_error_types:
        return True

    # 检查错误消息中是否包含网络相关关键词
    msg = str(exc).lower()
    network_keywords = ("connection error", "connection refused", "connect timeout", "timed out")
    return any(kw in msg for kw in network_keywords)


def _create_safe_default_manager_result() -> ManagerResult:
    """
    创建一个保证有效的默认 ManagerResult（终极兜底）

    当所有解析方法都失败时，返回一个"无更新"的安全实例，
    让决策树基于已有槽位继续流转，而不是崩溃。
    """
    return ManagerResult(
        slot_updates={},
        patient_emotion="calm",
        slot_valid=False,
        reasoning="解析失败，无法提取槽位信息",
    )


def _parse_manager_response(raw_output: str) -> Dict[str, Any]:
    """
    解析 Manager 的 JSON 响应（兜底方法，当结构化输出失败时使用）

    Args:
        raw_output: LLM 原始输出

    Returns:
        Dict: 解析后的决策数据
    """
    try:
        # 尝试提取 JSON (支持 markdown 代码块)
        json_match = re.search(r"```json\s*(.*?)\s*```", raw_output, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # 尝试直接解析原始输出
            json_str = raw_output.strip()

        data = json.loads(json_str)
        return {
            "slot_updates": data.get("slot_updates", {}),
            "patient_emotion": data.get("patient_emotion", "calm"),
            "slot_valid": data.get("slot_valid", True),
            "reasoning": data.get("reasoning", ""),
        }

    except Exception:
        # 解析失败，返回空
        return {
            "slot_updates": {},
            "patient_emotion": "calm",
            "slot_valid": False,
            "reasoning": f"JSON 解析失败: {raw_output[:200]}",
        }


def _get_conversation_history(messages: List[AnyMessage], max_turns: int = 10) -> List[Dict]:
    """
    获取对话历史（用于 Prompt）

    Args:
        messages: 消息列表
        max_turns: 最大轮数

    Returns:
        List[Dict]: 对话历史
    """
    history = []
    for msg in messages[-max_turns * 2 :]:
        if isinstance(msg, HumanMessage):
            history.append({"type": "human", "content": msg.content})
        elif isinstance(msg, AIMessage):
            history.append({"type": "ai", "content": msg.content[:500]})  # 截断过长内容
    return history


def _get_last_human_message(messages: List[AnyMessage]) -> str:
    """获取最后一条用户消息"""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            return msg.content or ""
    return ""


def manager_node(
    state: MouthCavityV2State,
    runtime: Runtime,
) -> Dict[str, Any]:
    """
    Manager 节点 - 槽位解析 + 决策树控制

    职责分离：
    - LLM：解析用户输入、提取槽位值、判断槽位有效性
    - 决策树：根据已收集槽位决定下一步操作

    Args:
        state: 当前状态
        runtime: 运行时上下文

    Returns:
        Dict: 状态更新
    """
    # 获取上下文资源
    logger = getattr(runtime.context, "logger", None)
    get_node_llm = getattr(runtime.context, "get_node_llm", None)

    if logger:
        logger.info("═══════════════════════════════════════")
        logger.info("🧠 Manager Node 开始 (混合模式：LLM解析 + 决策树控制)")

    messages = state.get("messages", [])
    current_flow_id = state.get("current_flow_id", "")
    current_slots = state.get("slots", {})
    debug_mode = state.get("debug_mode", False)
    pending_slot = state.get("pending_slot", "")
    triage_complete = state.get("triage_complete", False)

    # ================================================================
    # Flow 完成后的处理：根据意图类型区分处理
    # ================================================================
    last_user_message = _get_last_human_message(messages)
    intent_type = state.get("intent_type", "")

    if triage_complete and last_user_message:
        if logger:
            logger.info(f"✅ Flow 已完成，当前意图: {intent_type}")

        intent_subtype = state.get("intent_subtype", "")

        # 情况0: 用户请求"重新评估"
        # -> 重置 flow 状态，从头开始收集槽位
        if intent_type == "flow_related" and intent_subtype == "reassess":
            if logger:
                logger.info("🔄 用户请求重新评估，重置 flow 状态")
                logger.info("═══════════════════════════════════════")

            return {
                "action": "ask_slot",
                "action_params": {"slot_id": "cause_trigger"},
                "pending_slot": "cause_trigger",
                "slots": {},  # 清空槽位
                "current_flow_id": "",  # 彻底清空当前流程，允许重新识别
                "flow_initialized": False,  # 重置初始化标志
                "triage_complete": False,  # 重置完成标志
                "risk_level": "",  # 清空风险等级
                "care_plan_id": "",  # 清空护理方案 ID
                "manager_thought": "用户请求重新评估，彻底重置状态并从头开始",
            }

        # 情况1: 用户意图与当前 flow 相关（如"一直出血"、"我现在可以压迫了"）
        # -> 解析用户输入，更新槽位，重新评估，使用 RAG 回复
        if intent_type == "flow_related":
            if logger:
                logger.info("📋 用户意图与当前 flow 相关，尝试解析槽位更新并重新评估")

            # 获取流程实例
            try:
                flow = FlowRegistry.get(current_flow_id)
            except ValueError:
                flow = None

            # 尝试用 LLM 解析用户输入中的槽位更新
            llm_decision = None
            if flow and get_node_llm:
                try:
                    system_prompt = _load_prompt("manager_system.md")
                    user_prompt_template = _load_prompt("manager_user.md")

                    system_prompt_rendered = _render_template(
                        system_prompt,
                        flow_name=flow.flow_name,
                    )

                    user_prompt_rendered = _render_template(
                        user_prompt_template,
                        flow_name=flow.flow_name,
                        slots=[s.to_prompt_dict() for s in flow.slots],
                        current_slots=current_slots,
                        slots_summary=flow.get_slots_summary(current_slots),
                        conversation_history=_get_conversation_history(messages),
                        user_message=last_user_message,
                        pending_slot="",  # 没有特定待收集槽位
                    )

                    llm = get_node_llm("manager_node", runtime)
                    prompt = [
                        SystemMessage(content=system_prompt_rendered),
                        HumanMessage(content=user_prompt_rendered),
                    ]

                    # 使用结构化输出（与 intent_router_node 一致的模式）
                    manager_result: Optional[ManagerResult] = None
                    try:
                        llm_no_thinking = llm.bind(extra_body={"enable_thinking": False})
                        llm_structured = llm_no_thinking.with_structured_output(ManagerResult)
                        manager_result = llm_structured.invoke(prompt)
                        if logger:
                            logger.info(f"📥 结构化输出成功: {manager_result.model_dump()}")
                    except Exception as e:
                        is_net_err = _is_network_error(e)
                        if is_net_err:
                            if logger:
                                logger.error(f"❌ 网络连接异常，无法调用 LLM: {type(e).__name__}: {str(e)[:200]}")
                            manager_result = _create_safe_default_manager_result()
                        else:
                            # 非网络错误，回退到字符串解析
                            if logger:
                                logger.warning(f"⚠️ 结构化输出失败，回退到字符串解析: {type(e).__name__}: {str(e)[:200]}")
                            try:
                                response = llm.invoke(prompt)
                                parsed = _parse_manager_response(response.content)
                                manager_result = ManagerResult(**parsed)
                                if logger:
                                    logger.info(f"✅ 字符串解析成功: {manager_result.model_dump()}")
                            except Exception as inner_e:
                                if logger:
                                    logger.error(f"❌ 字符串解析也失败: {type(inner_e).__name__}: {str(inner_e)[:200]}")
                                manager_result = _create_safe_default_manager_result()

                    # 将 ManagerResult 转换为 llm_decision 字典
                    llm_decision = {
                        "slot_updates": {
                            k: v.model_dump() for k, v in manager_result.slot_updates.items()
                        },
                        "patient_emotion": manager_result.patient_emotion,
                        "slot_valid": manager_result.slot_valid,
                        "reasoning": manager_result.reasoning,
                    }

                    if logger:
                        logger.info(f"📊 LLM 解析结果: {llm_decision.get('slot_updates', {})}")

                except Exception as e:
                    if logger:
                        logger.warning(f"解析槽位更新失败: {e}")

            # 如果有槽位更新，合并并重新评估
            if llm_decision and llm_decision.get("slot_updates") and llm_decision.get("slot_valid", True):
                normalized_updates = normalize_all_slots(llm_decision["slot_updates"])
                if normalized_updates:
                    current_slots = merge_slots(current_slots, normalized_updates)
                    if logger:
                        logger.info(f"🔄 更新槽位: {normalized_updates}")

                    # 重新运行决策树
                    tree_decision = decide_next_step(current_slots, debug_mode)

                    if logger:
                        logger.info(f"🌳 重新评估结果: action={tree_decision['action']}, risk={tree_decision.get('risk_level', 'N/A')}")

                    # 如果决策树输出了新的响应（respond），更新风险等级
                    if tree_decision["action"] == "respond":
                        new_risk_level = tree_decision.get("risk_level", "")
                        new_care_plan_id = tree_decision.get("care_plan_id", "")

                        if logger:
                            logger.info(f"✅ 风险等级已更新: {new_risk_level}")
                            logger.info("═══════════════════════════════════════")

                        # 使用 RAG 回答，不透露风险等级
                        return {
                            "action": "rag_query",
                            "action_params": {"query": last_user_message},
                            "slots": current_slots,
                            "risk_level": new_risk_level,
                            "care_plan_id": new_care_plan_id,
                            "manager_thought": "用户提供新信息，风险等级已更新，使用知识库提供护理指导",
                        }

            # 没有槽位更新或解析失败，使用 RAG 回答后续问题
            if logger:
                logger.info("📚 使用 RAG 回答后续问题")
                logger.info("═══════════════════════════════════════")

            return {
                "action": "rag_query",
                "action_params": {"query": last_user_message},
                "manager_thought": "用户继续咨询出血相关问题，使用知识库提供护理指导",
            }

        # 情况2: 用户意图是切换到其他话题或查询术后护理等
        # -> 使用 RAG 回答
        else:
            if logger:
                logger.info("📚 使用 RAG 回答后续问题")
                logger.info("═══════════════════════════════════════")

            return {
                "action": "rag_query",
                "action_params": {"query": last_user_message},
                "manager_thought": "分诊已完成，使用知识库回答后续咨询",
            }

    # ================================================================
    # 第零层：Flow Switch 意图处理
    # ================================================================
    # 处理 flow_switch 意图：用户在当前流程中提到了其他话题
    if intent_type == "flow_switch":
        target_flow = state.get("target_flow", "")
        if logger:
            logger.info(f"🔄 检测到 flow_switch 意图，target_flow: {target_flow or '无'}")

        # 检查目标流程是否有效
        if target_flow and FlowRegistry.is_registered(target_flow):
            # 有效的目标流程 → 切换流程，重置槽位
            if logger:
                logger.info(f"✅ 切换到流程: {target_flow}")
                logger.info("═══════════════════════════════════════")

            return {
                "current_flow_id": target_flow,
                "flow_initialized": True,
                "slots": {},  # 清空槽位
                "pending_slot": "",
                "triage_complete": False,
                "action": "ask_slot",
                "action_params": {"slot_id": "cause_trigger", "care_context": "greeting"},
                "manager_thought": f"用户切换话题到 {target_flow}，从头开始收集槽位",
            }
        else:
            # 无效的目标流程（用户问的话题不在已注册流程中）→ 使用 RAG 回答
            if logger:
                logger.info(f"⚠️ 目标流程无效或未注册，使用 RAG 回答")
                logger.info("═══════════════════════════════════════")

            return {
                "action": "rag_query",
                "action_params": {"query": last_user_message},
                "manager_thought": "用户话题不在已知流程中，使用知识库回答",
            }

    # ================================================================
    # 第一层：Agent 宪法检查（框架层拦截）
    # ================================================================

    emergency = AgentInvariants.check_emergency(last_user_message)
    if emergency:
        if logger:
            logger.warning(f"🚨 紧急情况触发: {emergency.action_type}")
        return AgentInvariants.get_emergency_response(emergency)

    urgent_referral = AgentInvariants.check_urgent_referral(last_user_message)
    if urgent_referral:
        if logger:
            logger.warning(f"⚠️ 紧急转诊触发")
        return {
            "action": "final_response",
            "action_params": {"message": urgent_referral},
            "risk_level": "MEDIUM",
        }

    # ================================================================
    # 流程识别
    # ================================================================
    if not current_flow_id:
        # 尝试识别流程
        identified_flow = FlowRegistry.identify_flow(last_user_message)
        if identified_flow:
            current_flow_id = identified_flow
            if logger:
                logger.info(f"🎯 识别到流程: {current_flow_id}")
        else:
            # 未识别到任何流程，使用 RAG 问答模式（不再默认使用 bleeding 流程）
            if logger:
                logger.info("📚 未识别到特定流程，进入知识库问答模式")
                logger.info("═══════════════════════════════════════")
            return {
                "action": "rag_query",
                "action_params": {"query": last_user_message},
                "manager_thought": "未识别到特定流程，进入知识库问答模式",
            }

    # 获取流程实例
    try:
        flow = FlowRegistry.get(current_flow_id)
    except ValueError:
        return {
            "action": "fallback",
            "action_params": {"message": "抱歉，当前无法处理您的问题。"},
            "manager_thought": f"流程 {current_flow_id} 未注册",
        }

    # ================================================================
    # 第二层：LLM 槽位解析（只负责理解用户输入）
    # ================================================================
    llm_decision = None

    # 只有当有 pending_slot 且有用户消息时才调用 LLM 解析
    if pending_slot and last_user_message:
        try:
            system_prompt = _load_prompt("manager_system.md")
            user_prompt_template = _load_prompt("manager_user.md")
        except FileNotFoundError as e:
            if logger:
                logger.error(f"Prompt 文件加载失败: {e}")
            # 继续使用决策树，不阻塞流程

        # 渲染 Prompt
        system_prompt_rendered = _render_template(
            system_prompt,
            flow_name=flow.flow_name,
        )

        user_prompt_rendered = _render_template(
            user_prompt_template,
            flow_name=flow.flow_name,
            slots=[s.to_prompt_dict() for s in flow.slots],
            current_slots=current_slots,
            slots_summary=flow.get_slots_summary(current_slots),
            conversation_history=_get_conversation_history(messages),
            user_message=last_user_message,
            pending_slot=pending_slot,
        )

        # 调用 LLM
        if get_node_llm:
            llm = get_node_llm("manager_node", runtime)
        else:
            llm = getattr(runtime.context, "llm", None)

        if llm:
            prompt = [
                SystemMessage(content=system_prompt_rendered),
                HumanMessage(content=user_prompt_rendered),
            ]

            if logger:
                logger.info(f"📤 调用 LLM 解析用户输入（结构化输出）...")

            # 使用结构化输出（与 intent_router_node 一致的模式）
            manager_result: Optional[ManagerResult] = None
            try:
                # 显式关闭 Thinking 模式，避免 JSON 被截断
                llm_no_thinking = llm.bind(extra_body={"enable_thinking": False})
                llm_structured = llm_no_thinking.with_structured_output(ManagerResult)
                manager_result = llm_structured.invoke(prompt)
                if logger:
                    logger.info(f"📥 结构化输出成功: {manager_result.model_dump()}")
            except Exception as e:
                is_net_err = _is_network_error(e)
                if is_net_err:
                    # 网络错误：直接使用默认兜底
                    if logger:
                        logger.error(f"❌ 网络连接异常，无法调用 LLM: {type(e).__name__}: {str(e)[:200]}")
                    manager_result = _create_safe_default_manager_result()
                else:
                    # 非网络错误，回退到字符串解析
                    if logger:
                        logger.warning(f"⚠️ 结构化输出失败，回退到字符串解析: {type(e).__name__}: {str(e)[:200]}")
                    try:
                        response = llm.invoke(prompt)
                        parsed = _parse_manager_response(response.content)
                        manager_result = ManagerResult(**parsed)
                        if logger:
                            logger.info(f"✅ 字符串解析成功: {manager_result.model_dump()}")
                    except Exception as inner_e:
                        is_inner_net_err = _is_network_error(inner_e)
                        if logger:
                            label = "网络异常" if is_inner_net_err else "解析失败"
                            logger.error(f"❌ 字符串解析也失败（{label}）: {type(inner_e).__name__}: {str(inner_e)[:200]}")
                        manager_result = _create_safe_default_manager_result()

            # 将 ManagerResult 转换为 llm_decision 字典
            llm_decision = {
                "slot_updates": {
                    k: v.model_dump() for k, v in manager_result.slot_updates.items()
                },
                "patient_emotion": manager_result.patient_emotion,
                "slot_valid": manager_result.slot_valid,
                "reasoning": manager_result.reasoning,
            }

            if logger:
                logger.info(f"📊 LLM 解析结果: slot_updates={llm_decision['slot_updates']}, valid={llm_decision.get('slot_valid', True)}")

            # 检查槽位有效性：只有当 slot_valid 为 true 时才更新槽位
            slot_valid = llm_decision.get("slot_valid", True)
            if not slot_valid:
                if logger:
                    logger.warning(f"⚠️ 槽位无效，用户回答不相关: {llm_decision.get('reasoning', '')}")
                # 槽位无效时，不更新槽位，继续用当前槽位进入决策树
                # 决策树会重新询问当前待收集的槽位

            # 合并槽位更新（先进行后处理解析，确保值标准化）
            elif llm_decision["slot_updates"]:
                normalized_updates = normalize_all_slots(llm_decision["slot_updates"])
                if logger:
                    logger.info(f"📊 槽位标准化: {llm_decision['slot_updates']} -> {normalized_updates}")
                current_slots = merge_slots(current_slots, normalized_updates)

    # ================================================================
    # 第三层：决策树决定下一步操作
    # ================================================================
    if logger:
        logger.info(f"🌳 决策树输入: slots={list(current_slots.keys())}")

    tree_decision = decide_next_step(current_slots, debug_mode)

    if logger:
        logger.info(f"🌳 决策树输出: action={tree_decision['action']}, slot_id={tree_decision.get('slot_id', 'N/A')}")
        logger.info("═══════════════════════════════════════")

    # ================================================================
    # 构建状态更新
    # ================================================================
    state_update: Dict[str, Any] = {
        "current_flow_id": current_flow_id,
        "flow_initialized": True,
        "slots": current_slots,
        "patient_emotion": llm_decision["patient_emotion"] if llm_decision else "calm",
        "manager_thought": llm_decision["reasoning"] if llm_decision else "决策树自动流转",
    }

    # 根据决策树结果设置 action
    if tree_decision["action"] == "ask_slot":
        state_update["action"] = "ask_slot"
        state_update["action_params"] = {
            "slot_id": tree_decision["slot_id"],
        }
        state_update["pending_slot"] = tree_decision["slot_id"]

        # 传递额外参数
        if "guidance_type" in tree_decision:
            state_update["action_params"]["guidance_type"] = tree_decision["guidance_type"]
        if "care_context" in tree_decision:
            state_update["action_params"]["care_context"] = tree_decision["care_context"]

    elif tree_decision["action"] == "respond":
        state_update["action"] = "final_response"
        state_update["action_params"] = {
            "care_plan_id": tree_decision.get("care_plan_id", ""),
            "prompt_hint": tree_decision.get("prompt_hint", ""),
        }
        state_update["risk_level"] = tree_decision.get("risk_level")
        state_update["pending_slot"] = ""  # 清空

    # 调试模式附加信息
    if debug_mode:
        state_update["operator_log"] = f"决策树: {json.dumps(tree_decision, ensure_ascii=False, default=str)}"

    return state_update


def route_decision(state: MouthCavityV2State, runtime: Runtime) -> str:
    """
    路由决策

    根据 Manager 的 action 决定下一步执行哪个 Operator。

    Args:
        state: 当前状态
        runtime: 运行时上下文

    Returns:
        str: 下一个节点名称
    """
    # 检查紧急情况
    if state.get("is_emergency"):
        return "emergency"

    action = state.get("action", "")

    if action == "ask_slot":
        return "ask_slot"
    elif action == "rag_query":
        return "rag"
    elif action == "assess_risk":
        return "risk_assessment"
    elif action == "final_response":
        return "final"
    elif action == "emergency":
        return "emergency"
    else:
        return "fallback"
