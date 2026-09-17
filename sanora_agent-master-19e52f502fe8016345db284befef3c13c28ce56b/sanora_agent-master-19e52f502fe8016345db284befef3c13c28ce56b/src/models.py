from pydantic import BaseModel, Field
from typing import List, Optional, Union, Dict, Any
from enum import Enum


class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    FUNCTION = "function"
    TOOL = "tool"


class RiskLevel(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RebuildTarget(str, Enum):
    """重建目标类型"""

    DOCUMENTS = "documents"
    QA_PAIRS = "qa_pairs"
    ALL = "all"


class Message(BaseModel):
    role: MessageRole
    content: str
    name: Optional[str] = None
    additional_kwargs: Optional[Dict[str, Any]] = None


class ChatRequest(BaseModel):
    messages: List[Message]
    model: Optional[str] = None
    user: str = Field(..., min_length=1, description="用户ID/设备ID（必填）")
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    stream: bool = False
    thread_id: Optional[str] = None
    reset_state: bool = False
    debug_mode: bool = False  # 新增: 控制问题前缀显示和槽位信息返回
    user_response: Optional[str] = None  # 新增: 用户对中断的响应数据
    current_app: Optional[str] = None  # 新增: 当前应用名称
    current_page: Optional[str] = None  # 新增: 当前业务页面名称
    page_data: Optional[Dict[str, Any]] = None  # 新增: 客户端返回原始的数据结构
    order_history: Optional[List[Dict[str, Any]]] = None  # 新增: 历史订单信息
    current_page_elements: Optional[List[Dict[str, Any]]] = (
        None  # 新增: 可见可说，可操作元素
    )
    no_action_elements: Optional[List[Dict[str, Any]]] = None  # 新增: 不可操作元素
    user_info: Optional[Dict[str, Any]] = (
        None  # 新增: 用户信息（地址、出行时段、画像等）
    )
    navigation_info: Optional[Dict[str, Any]] = (
        None  # 新增: 导航信息（起点、终点、途经点等）
    )
    vehicle_info: Optional[Dict[str, Any]] = (
        None  # 新增: 车辆信息（档位、速度、温度、空调状态等）
    )
    order_info: Optional[List[Dict[str, Any]]] = (
        None  # 新增: 订单信息（广播文本、订单状态等）
    )
    other_region_data: Optional[List[Dict[str, Any]]] = None  # 新增: 其他区域数据
    other_region_context: Optional[List[Dict[str, Any]]] = None  # 新增: 其他区域上下文


class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class Choice(BaseModel):
    index: int
    message: Optional[Message] = None
    delta: Optional[dict] = None
    finish_reason: Optional[str] = None  # 可以是 "stop", "length", "interrupt" 等


class ChatResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Choice]
    usage: Optional[Usage] = None


class ChatStreamResponse(BaseModel):
    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str
    choices: List[Choice]
    usage: Optional[Usage] = None


class ErrorResponse(BaseModel):
    error: Dict[str, Any]


class ModelInfo(BaseModel):
    id: str
    object: str = "model"
    created: int
    owned_by: str = "rooyee"
    provider: Optional[str] = None


class ModelsResponse(BaseModel):
    object: str = "list"
    data: List[ModelInfo]


class RebuildRequest(BaseModel):
    """重建知识库的请求体"""

    target: RebuildTarget = Field(
        default=RebuildTarget.ALL, description="重建目标：documents/qa_pairs/all"
    )
    knowledge_base_path: Optional[str] = Field(
        default=None,
        description="动态指定文档路径（可选）。如果提供，将覆盖 pack.yaml 中的 knowledge_base 配置",
    )


class QAPairCreateRequest(BaseModel):
    """创建问答对的请求体"""

    question: str = Field(..., min_length=1, description="用户问题")
    answer: str = Field(..., min_length=1, description="系统答案")
    session_id: Optional[str] = Field(default=None, description="来源会话ID（可选）")
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="额外元数据（可选），如 user_id、feedback 等"
    )
    # 追责字段
    editor_id: Optional[int] = Field(default=None, description="编辑人 ID")
    editor_name: Optional[str] = Field(default=None, description="编辑人用户名")
    edited_at: Optional[str] = Field(default=None, description="编辑时间 (ISO格式)")
