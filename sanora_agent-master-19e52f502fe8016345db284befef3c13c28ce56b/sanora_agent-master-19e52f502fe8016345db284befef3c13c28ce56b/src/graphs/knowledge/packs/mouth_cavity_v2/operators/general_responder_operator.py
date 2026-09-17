"""
General Responder Operator - 通用回复

处理 general_query 类型的意图：
- self_intro: 使用固定模板回复
- capabilities: 使用固定模板回复
- other: 调用 LLM 生成回复
"""

from pathlib import Path
from typing import Any, Dict

import yaml
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.runtime import Runtime

from ..core import MouthCavityV2State


# Prompt 文件路径
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def _load_prompt(filename: str) -> str:
    """加载 Prompt 文件"""
    path = PROMPTS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8")


def _load_responses() -> Dict[str, Any]:
    """加载固定回复模板"""
    path = PROMPTS_DIR / "general_responses.yaml"
    if not path.exists():
        return {}
    
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _get_last_human_message(messages) -> str:
    """获取最后一条用户消息"""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            return msg.content or ""
    return ""


def general_responder_operator(
    state: MouthCavityV2State,
    runtime: Runtime,
) -> Dict[str, Any]:
    """
    通用回复 Operator
    
    根据 intent_subtype 选择回复方式：
    - self_intro/capabilities/greeting: 使用固定模板
    - other: 调用 LLM 生成回复
    
    Args:
        state: 当前状态
        runtime: 运行时上下文
        
    Returns:
        Dict: 状态更新
    """
    logger = getattr(runtime.context, "logger", None)
    get_node_llm = getattr(runtime.context, "get_node_llm", None)
    
    if logger:
        logger.info("═══════════════════════════════════════")
        logger.info("💬 General Responder Operator 开始")
    
    intent_subtype = state.get("intent_subtype", "")
    messages = state.get("messages", [])
    
    if logger:
        logger.info(f"📌 意图子类型: {intent_subtype}")
    
    # ================================================================
    # 固定模板回复
    # ================================================================
    responses = _load_responses()
    
    if intent_subtype in responses:
        template = responses[intent_subtype]
        response_text = template.get("response", "")
        
        if response_text:
            if logger:
                logger.info(f"📝 使用固定模板回复: {intent_subtype}")
                logger.info("═══════════════════════════════════════")
            
            return {
                "messages": [AIMessage(content=response_text)],
            }
    
    # ================================================================
    # LLM 回复（other 类型或模板不存在）
    # ================================================================
    if logger:
        logger.info("🤖 使用 LLM 生成回复")
    
    if get_node_llm:
        llm = get_node_llm("general_responder_operator", runtime)
    else:
        llm = getattr(runtime.context, "llm", None)
    
    if not llm:
        if logger:
            logger.warning("⚠️ 无可用 LLM，使用兜底回复")
        
        return {
            "messages": [
                AIMessage(
                    content="您好！我是北大口腔四门诊的术后护理助手。请问有什么可以帮助您的？"
                )
            ],
        }
    
    # 加载角色 Prompt
    try:
        system_prompt = _load_prompt("general_responder_system.md")
    except FileNotFoundError:
        system_prompt = "你是北大口腔四门诊的种植牙术后患者管理智能AI助手。"
    
    last_user_message = _get_last_human_message(messages)
    
    # 调用 LLM
    prompt = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=last_user_message),
    ]
    
    response = llm.invoke(prompt)
    
    if logger:
        logger.info(f"📥 LLM 响应: {response.content[:100]}")
        logger.info("═══════════════════════════════════════")
    
    return {
        "messages": [AIMessage(content=response.content)],
    }
