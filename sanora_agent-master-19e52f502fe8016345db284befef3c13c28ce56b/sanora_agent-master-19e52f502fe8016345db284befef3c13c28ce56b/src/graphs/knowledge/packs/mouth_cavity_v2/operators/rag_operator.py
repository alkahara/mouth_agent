"""
RAGOperator - 知识库查询 Operator

负责调用知识库 RAG 回答用户的非结构化问题。
"""

import json
from pathlib import Path
from typing import Any, Dict

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.runtime import Runtime

from ..core import FlowRegistry, MouthCavityV2State


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


def rag_operator(
    state: MouthCavityV2State,
    runtime: Runtime,
) -> Dict[str, Any]:
    """
    知识库查询 Operator

    调用知识库 RAG 回答用户问题。

    Args:
        state: 当前状态
        runtime: 运行时上下文

    Returns:
        Dict: 状态更新（包含 AIMessage）
    """
    logger = getattr(runtime.context, "logger", None)
    get_node_llm = getattr(runtime.context, "get_node_llm", None)

    if logger:
        logger.info("📚 RAG Operator 开始")

    action_params = state.get("action_params", {})
    query = action_params.get("query", "")

    if not query:
        return {
            "messages": [AIMessage(content="抱歉，我没有理解您的问题。请再说一遍？")],
        }

    # 获取 RAG 资源（从 runtime.context 获取）
    retriever = getattr(runtime.context, "retriever", None)

    retrieved_docs = ""

    # 尝试使用 retriever 检索文档
    if retriever:
        try:
            # 使用新版 LangChain API：invoke 替代已弃用的 get_relevant_documents
            docs = retriever.invoke(query)
            retrieved_docs = "\n\n".join([doc.page_content for doc in docs[:5]])
            if logger:
                logger.info(f"📖 检索到 {len(docs)} 篇文档")
        except Exception as e:
            if logger:
                logger.warning(f"检索失败: {e}")

    # 使用 LLM 生成回答
    try:
        if get_node_llm:
            llm = get_node_llm("rag_operator", runtime)
            
            if retrieved_docs:
                # 有检索文档，使用 RAG prompt
                prompt_template = _load_prompt("rag_query.md")
                prompt = _render_template(
                    prompt_template,
                    retrieved_docs=retrieved_docs,
                    user_query=query,
                )
            else:
                # 没有检索到文档，直接用 LLM 回答（fallback 模式）
                if logger:
                    logger.info("📝 未检索到相关文档，使用 LLM 直接回答")
                prompt = f"""你是口腔术后护理专家。用户询问："{query}"

请根据你的专业知识回答这个问题。如果这个问题超出你的专业范围或需要更详细的医疗诊断，请友好地建议用户咨询医生。

要求：
1. 回答要专业但通俗易懂
2. 如果涉及可能的风险，要明确提示
3. 避免使用过于绝对的表述，使用"可能"、"建议"等措辞

直接输出回答内容。"""

            response = llm.invoke([HumanMessage(content=prompt)])
            return {
                "messages": [AIMessage(content=response.content)],
            }
    except Exception as e:
        if logger:
            logger.error(f"生成回答失败: {e}")

    # Fallback（只有当 LLM 也失败时才返回此错误）
    return {
        "messages": [AIMessage(content="抱歉，暂时无法处理您的问题，请稍后再试或联系医生获取专业指导。")],
    }
