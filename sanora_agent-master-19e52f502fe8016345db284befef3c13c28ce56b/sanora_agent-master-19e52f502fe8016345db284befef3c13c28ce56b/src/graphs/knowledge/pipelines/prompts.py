"""Default prompt templates for agentic knowledge pipelines."""

DEFAULT_SYSTEM_PROMPT = (
    "你是一名专业的知识助手，需要根据给定的上下文回答用户问题。"
    "如果上下文不足以回答，请坦诚告知并建议用户稍后再试。"
)

DEFAULT_USER_PROMPT = (
    "用户问题：{question}\n"
    "相关上下文：{context}\n"
    "请结合上下文输出简洁、准确的回答。"
)

__all__ = ["DEFAULT_SYSTEM_PROMPT", "DEFAULT_USER_PROMPT"]
