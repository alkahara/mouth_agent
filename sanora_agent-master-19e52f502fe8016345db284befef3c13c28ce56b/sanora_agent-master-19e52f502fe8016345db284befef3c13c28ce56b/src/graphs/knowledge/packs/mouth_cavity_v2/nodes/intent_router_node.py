"""
Intent Router Node - 意图路由节点

在进入 Manager 之前判断用户意图：
- flow_related: 与当前 flow 相关，继续槽位收集
- general_query: 通用问题，使用固定模板或 LLM 回复
- flow_switch: 切换到其他 flow
"""

import json
import re
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage
from langgraph.runtime import Runtime
from pydantic import BaseModel, Field

from ..core import FlowRegistry, MouthCavityV2State


# ================================================================
# Pydantic Model 定义（用于 LLM 结构化输出）
# ================================================================

class IntentResult(BaseModel):
    """意图识别结果模型"""

    intent_type: Literal["flow_related", "general_query", "flow_switch"] = Field(
        default="flow_related",
        description="意图类型: flow_related=与当前流程相关, general_query=通用问题, flow_switch=切换流程",
    )
    intent_subtype: str = Field(
        default="",
        description="意图子类型: self_intro=自我介绍, capabilities=能力介绍, reassess=重新评估, 其他为空",
    )
    target_flow: str = Field(
        default="",
        description="目标流程ID（仅当 intent_type=flow_switch 时填写）",
    )
    reasoning: str = Field(
        default="",
        description="判断依据（简要说明）",
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


def _get_last_human_message(messages: List[AnyMessage]) -> str:
    """获取最后一条用户消息"""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            return msg.content or ""
    return ""


def _get_conversation_history(messages: List[AnyMessage], max_turns: int = 6) -> List[Dict]:
    """获取对话历史"""
    from langchain_core.messages import AIMessage
    
    history = []
    for msg in messages[-max_turns * 2:]:
        if isinstance(msg, HumanMessage):
            history.append({"type": "human", "content": msg.content})
        elif isinstance(msg, AIMessage):
            history.append({"type": "ai", "content": msg.content[:300]})
    return history


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


def _create_safe_default_intent(network_error: bool = False) -> IntentResult:
    """
    创建一个保证有效的默认 IntentResult（终极兜底）

    Args:
        network_error: 如果为 True，表示因网络问题导致失败

    当所有解析方法都失败时：
    - 网络错误 → general_query.network_error（提示网络问题）
    - 其他错误 → general_query.parse_error（提示无法理解）

    注意：正常的闲聊会被识别为 general_query.other，会调用 LLM 生成回复。

    Returns:
        IntentResult: 默认为 general_query.parse_error 或 network_error 的安全实例
    """
    if network_error:
        return IntentResult(
            intent_type="general_query",
            intent_subtype="network_error",
            target_flow="",
            reasoning="网络连接异常，无法调用 LLM",
        )
    return IntentResult(
        intent_type="general_query",
        intent_subtype="parse_error",
        target_flow="",
        reasoning="解析失败，请用户重新表述",
    )


def _parse_intent_response(raw_output: str) -> Dict[str, Any]:
    """
    解析 Intent Router 的 JSON 响应（兜底方法，当结构化输出失败时使用）
    """
    try:
        # 尝试提取 JSON (支持 markdown 代码块)
        json_match = re.search(r"```json\s*(.*?)\s*```", raw_output, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = raw_output.strip()

        data = json.loads(json_str)
        return {
            "intent_type": data.get("intent_type", "flow_related"),
            "intent_subtype": data.get("intent_subtype", ""),
            "target_flow": data.get("target_flow", ""),
            "reasoning": data.get("reasoning", ""),
        }

    except Exception:
        # 解析失败，默认为 flow_related
        return {
            "intent_type": "flow_related",
            "intent_subtype": "",
            "target_flow": "",
            "reasoning": f"JSON 解析失败: {raw_output[:100]}",
        }


def _quick_intent_check(user_message: str) -> Optional[Dict[str, Any]]:
    """
    快速意图检测（不需要调用 LLM）

    仅用于明确的、高频的模式匹配（问候、能力询问、重新评估）。
    其他闲聊交给 LLM 处理。
    """
    message_lower = user_message.lower().strip()

    # ================================================================
    # 优先级0：检查是否是"重新评估"请求（明确意图）
    # ================================================================
    reassess_patterns = ["重新评估", "再评估一次", "重新开始", "重来"]
    for pattern in reassess_patterns:
        if pattern in message_lower:
            return {
                "intent_type": "flow_related",
                "intent_subtype": "reassess",
                "target_flow": "",
                "reasoning": f"快速匹配: 重新评估模式 '{pattern}'",
            }

    # ================================================================
    # 优先级1：检查是否包含 flow 触发关键词（紧急情况优先）
    # ================================================================
    # 如果消息中包含flow关键词（如"出血"、"血"等），不应该被其他逻辑拦截
    # 这里返回 None，让后续逻辑通过 identify_flow 来处理
    identified_flow = FlowRegistry.identify_flow(user_message)
    if identified_flow:
        # 发现flow关键词，跳过快速检测，让后续逻辑处理
        return None

    # ================================================================
    # 优先级2：高频问候/能力询问（快速响应，减少 LLM 调用）
    # ================================================================
    # 问候模式（仅当是纯粹问候，且消息很短时）
    greeting_patterns = ["你好", "您好", "hello", "hi", "嗨"]
    if message_lower in greeting_patterns or (
        len(message_lower) <= 5 and any(p in message_lower for p in greeting_patterns)
    ):
        return {
            "intent_type": "general_query",
            "intent_subtype": "greeting",
            "target_flow": "",
            "reasoning": "快速匹配: 问候模式",
        }

    # 自我介绍模式
    self_intro_patterns = ["你是谁", "你是什么", "介绍下你自己", "介绍一下你自己", "你叫什么", "你的名字", "自我介绍"]
    for pattern in self_intro_patterns:
        if pattern in message_lower:
            return {
                "intent_type": "general_query",
                "intent_subtype": "self_intro",
                "target_flow": "",
                "reasoning": f"快速匹配: 自我介绍模式 '{pattern}'",
            }

    # 能力介绍模式
    capabilities_patterns = ["你能做什么", "你有什么功能", "你会什么", "可以帮我做什么", "你能帮我", "有什么用"]
    for pattern in capabilities_patterns:
        if pattern in message_lower:
            return {
                "intent_type": "general_query",
                "intent_subtype": "capabilities",
                "target_flow": "",
                "reasoning": f"快速匹配: 能力介绍模式 '{pattern}'",
            }

    # ================================================================
    # 其他情况：交给 LLM 判断
    # ================================================================
    return None


def intent_router_node(
    state: MouthCavityV2State,
    runtime: Runtime,
) -> Dict[str, Any]:
    """
    Intent Router 节点 - 意图路由
    
    判断用户输入的意图类型，决定后续处理路径。
    
    Args:
        state: 当前状态
        runtime: 运行时上下文
        
    Returns:
        Dict: 状态更新，包含 intent_type
    """
    logger = getattr(runtime.context, "logger", None)
    get_node_llm = getattr(runtime.context, "get_node_llm", None)
    
    if logger:
        logger.info("═══════════════════════════════════════")
        logger.info("🎯 Intent Router Node 开始")
    
    messages = state.get("messages", [])
    current_flow_id = state.get("current_flow_id", "")
    pending_slot = state.get("pending_slot", "")
    
    last_user_message = _get_last_human_message(messages)
    
    if logger:
        logger.info(f"📝 用户消息: {last_user_message[:100]}")
        logger.info(f"📌 当前 Flow: {current_flow_id or '无'}")
    
    # ================================================================
    # 快速意图检测（不需要 LLM）
    # ================================================================
    triage_complete = state.get("triage_complete", False)
    quick_result = _quick_intent_check(last_user_message)

    if quick_result:
        # 当 triage_complete=True 时，只有特定的 general_query 子类型才保留
        # 其他问题都应该走 RAG（仍属于当前 flow 上下文）
        if triage_complete and quick_result["intent_type"] == "general_query":
            subtype = quick_result.get("intent_subtype", "")
            # 只有 greeting/self_intro/capabilities 保留为 general_query
            # 其他问题（如"护理指导"）应该走 RAG
            if subtype not in ("greeting", "self_intro", "capabilities"):
                if logger:
                    logger.info(f"⚡ 快速匹配到 general_query.{subtype}，但 triage 已完成，转为 flow_related 走 RAG")
                    logger.info("═══════════════════════════════════════")
                return {
                    "intent_type": "flow_related",
                    "intent_subtype": "rag_query",
                }

        if logger:
            logger.info(f"⚡ 快速匹配成功: {quick_result['intent_type']}.{quick_result['intent_subtype']}")
            logger.info("═══════════════════════════════════════")
        
        return {
            "intent_type": quick_result["intent_type"],
            "intent_subtype": quick_result.get("intent_subtype", ""),
        }

    # ================================================================
    # triage 完成后：继续往下走让 LLM 判断意图
    # （不再使用硬编码关键词，让 LLM 判断是否与口腔相关）
    # ================================================================
    # 注：triage_complete 时会跳过后面的 flow 检测逻辑，直接进入 LLM 判断
    
    # ================================================================
    # 无活跃 flow 时：检查是否触发 flow
    # ================================================================
    if not current_flow_id:
        identified_flow = FlowRegistry.identify_flow(last_user_message)
        if identified_flow:
            if logger:
                logger.info(f"🎯 识别到 Flow: {identified_flow}")
                logger.info("═══════════════════════════════════════")
            
            return {
                "intent_type": "flow_related",
                "intent_subtype": "",
                "current_flow_id": identified_flow,
            }
    
    # ================================================================
    # 有活跃 flow 时：检查是否与当前 flow 相关
    # ================================================================
    if current_flow_id and pending_slot:
        # 检查是否是其他 flow 的触发词
        other_flow = FlowRegistry.identify_flow(last_user_message)
        if other_flow and other_flow != current_flow_id:
            if logger:
                logger.info(f"🔄 检测到 Flow 切换: {current_flow_id} -> {other_flow}")
                logger.info("═══════════════════════════════════════")

            return {
                "intent_type": "flow_switch",
                "intent_subtype": "",
                "target_flow": other_flow,
            }

        # 不再硬编码闲聊关键词和短消息判断，全部交给 LLM 判断
        # 继续往下走到 LLM 判断部分
    
    # ================================================================
    # 需要 LLM 判断的复杂情况
    # ================================================================
    if get_node_llm:
        llm = get_node_llm("intent_router_node", runtime)
    else:
        llm = getattr(runtime.context, "llm", None)
    
    if not llm:
        if logger:
            logger.warning("⚠️ 无可用 LLM，默认 flow_related")
        return {
            "intent_type": "flow_related",
            "intent_subtype": "",
        }
    
    try:
        system_prompt = _load_prompt("intent_router_system.md")
        user_prompt_template = _load_prompt("intent_router_user.md")
    except FileNotFoundError as e:
        if logger:
            logger.error(f"Prompt 加载失败: {e}")
        return {
            "intent_type": "flow_related",
            "intent_subtype": "",
        }
    
    # 获取可用 flow 信息
    available_flows = FlowRegistry.list_flow_info()
    
    # 获取当前 flow 名称
    current_flow_name = ""
    if current_flow_id:
        try:
            flow = FlowRegistry.get(current_flow_id)
            current_flow_name = flow.flow_name
        except ValueError:
            pass
    
    # 渲染 Prompt
    system_prompt_rendered = _render_template(
        system_prompt,
        available_flows=available_flows,
    )
    
    user_prompt_rendered = _render_template(
        user_prompt_template,
        current_flow_id=current_flow_id or "无",
        current_flow_name=current_flow_name or "无活跃流程",
        pending_slot=pending_slot or "无",
        triage_complete=triage_complete,
        triage_status="已完成，RAG 问答模式" if triage_complete else "进行中，槽位收集模式",
        conversation_history=_get_conversation_history(messages),
        user_message=last_user_message,
    )
    
    # 调用 LLM（使用 Pydantic 结构化输出）
    prompt = [
        SystemMessage(content=system_prompt_rendered),
        HumanMessage(content=user_prompt_rendered),
    ]
    
    if logger:
        logger.info("📤 调用 LLM 判断意图（结构化输出）...")
    
    # 尝试使用结构化输出
    intent_result: Optional[IntentResult] = None
    try:
        # 显式关闭 qwen-flash 的 Thinking 模式，避免模型生成大量思考内容
        # 导致输出 token 超出 max_tokens 限制，JSON 被截断而解析失败
        llm_no_thinking = llm.bind(extra_body={"enable_thinking": False})
        llm_structured = llm_no_thinking.with_structured_output(IntentResult)
        intent_result = llm_structured.invoke(prompt)
        if logger:
            logger.info(f"📥 结构化输出成功: {intent_result.model_dump()}")
    except Exception as e:
        # 判断是否为网络错误
        is_net_err = _is_network_error(e)

        if is_net_err:
            # 网络错误：直接使用 network_error 兜底，不再重试 LLM
            if logger:
                logger.error(f"❌ 网络连接异常，无法调用 LLM: {type(e).__name__}: {str(e)[:200]}")
            intent_result = _create_safe_default_intent(network_error=True)
            if logger:
                logger.warning(f"⚠️ 使用网络异常默认意图: {intent_result.model_dump()}")
        else:
            # 非网络错误，回退到字符串解析
            if logger:
                logger.warning(f"⚠️ 结构化输出失败，回退到字符串解析: {type(e).__name__}: {str(e)[:200]}")

            try:
                # 回退到传统方式
                response = llm.invoke(prompt)
                parsed = _parse_intent_response(response.content)
                intent_result = IntentResult(**parsed)
                if logger:
                    logger.info(f"✅ 字符串解析成功: {intent_result.model_dump()}")
            except Exception as inner_e:
                # 字符串解析也失败，检查是否为网络错误
                is_inner_net_err = _is_network_error(inner_e)
                if logger:
                    logger.error(f"❌ 字符串解析异常: {type(inner_e).__name__}: {str(inner_e)[:200]}")
                intent_result = _create_safe_default_intent(network_error=is_inner_net_err)
                if logger:
                    label = "网络异常" if is_inner_net_err else "解析失败"
                    logger.warning(f"⚠️ 使用{label}默认意图: {intent_result.model_dump()}")
    
    # 日志输出
    if logger:
        subtype = intent_result.intent_subtype
        intent_display = intent_result.intent_type
        if subtype and subtype != 'other':
            intent_display = f"{intent_display}.{subtype}"
        logger.info(f"🎯 意图判断结果: {intent_display}")
        logger.info("═══════════════════════════════════════")
    
    state_update: Dict[str, Any] = {
        "intent_type": intent_result.intent_type,
        "intent_subtype": intent_result.intent_subtype,
    }
    
    # 如果是 flow_switch，记录目标 flow
    if intent_result.intent_type == "flow_switch" and intent_result.target_flow:
        state_update["target_flow"] = intent_result.target_flow
    
    return state_update


def route_intent(state: MouthCavityV2State, runtime: Runtime) -> str:
    """
    Intent 路由函数
    
    根据 intent_type 决定下一个节点。
    """
    intent_type = state.get("intent_type", "")
    
    if intent_type == "general_query":
        return "general_responder"
    elif intent_type in ("flow_related", "flow_switch"):
        return "manager"
    else:
        return "manager"  # 默认进入 manager
