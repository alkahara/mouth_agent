#!/usr/bin/env python3
"""FastAPI proxy server exposing the ChatClient to the web UI."""

from __future__ import annotations

import os
import json
import re
import uuid
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

try:  # Pydantic v2
    from pydantic import ConfigDict
    PYDANTIC_V2 = True
except ImportError:  # Pydantic v1 fallback
    ConfigDict = None  # type: ignore
    PYDANTIC_V2 = False

from chat_client import ChatClient
from auth import (
    Token,
    TokenUser,
    User,
    create_access_token,
    get_current_user,
)
from database import get_db
from passwords import verify_password
from user_repository import DuplicateLoginCodeError, USER_STATUS_ACTIVE, UserRepository
from wechat_client import WeChatClient, WeChatLoginError

DEFAULT_BASE_URL = os.getenv("CHAT_BASE_URL", "http://127.0.0.1:8080")
_wechat_appid = os.getenv("WECHAT_APPID", "").strip()
_wechat_secret = os.getenv("WECHAT_SECRET", "").strip()
WECHAT_CLIENT = (
    WeChatClient(appid=_wechat_appid, secret=_wechat_secret)
    if _wechat_appid and _wechat_secret
    else None
)


class AgentName(str, Enum):
    DISNEY = "disney"
    MOUTH = "mouth"
    MOUTH_V2 = "mouth_v2"
    MOUTH_CAVITY_V2_KNOWLEDGE = "mouth_cavity_v2_knowledge"


DEFAULT_AGENT = AgentName.DISNEY


AGENT_PROFILES: Dict[AgentName, Dict[str, str]] = {
    AgentName.DISNEY: {
        "label": "迪士尼 Agent",
        "base_url": os.getenv("CHAT_DISNEY_BASE_URL", DEFAULT_BASE_URL),
        "api_key": os.getenv("CHAT_DISNEY_API_KEY", ""),
    },
    AgentName.MOUTH: {
        "label": "口腔 Agent",
        "base_url": os.getenv("CHAT_MOUTH_BASE_URL", DEFAULT_BASE_URL),
        "api_key": os.getenv("CHAT_MOUTH_API_KEY", ""),
    },
    AgentName.MOUTH_V2: {
        "label": "口腔 Agent V2",
        "base_url": os.getenv("CHAT_MOUTH_V2_BASE_URL", os.getenv("CHAT_MOUTH_BASE_URL", DEFAULT_BASE_URL)),
        "api_key": os.getenv("CHAT_MOUTH_V2_API_KEY", ""),
    },
    AgentName.MOUTH_CAVITY_V2_KNOWLEDGE: {
        "label": "口腔 V2 知识库",
        "base_url": os.getenv("CHAT_MOUTH_CAVITY_V2_KNOWLEDGE_BASE_URL", os.getenv("CHAT_MOUTH_BASE_URL", DEFAULT_BASE_URL)),
        "api_key": os.getenv("CHAT_MOUTH_CAVITY_V2_KNOWLEDGE_API_KEY", ""),
    },
}

PRESET_FILES: Dict[AgentName, Path] = {
    AgentName.DISNEY: Path(__file__).with_name("迪士尼-预设问题.txt"),
    AgentName.MOUTH: Path(__file__).with_name("口腔-预设问题.txt"),
    AgentName.MOUTH_V2: Path(__file__).with_name("口腔-预设问题.txt"),  # 复用口腔 v1 预设问题
    AgentName.MOUTH_CAVITY_V2_KNOWLEDGE: Path(__file__).with_name("口腔V2知识库-预设问题.txt"),
}


def get_agent_profile(agent: AgentName | None) -> Dict[str, str]:
    if agent and agent in AGENT_PROFILES:
        return AGENT_PROFILES[agent]
    return AGENT_PROFILES[DEFAULT_AGENT]



def _looks_like_binary_score(payload: str) -> bool:
    """Detect the binary_score metadata payload returned by some agents."""

    stripped = payload.strip()
    if not stripped.startswith("{"):
        return False
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError:
        return False

    if isinstance(data, dict) and set(data.keys()) == {"binary_score"}:
        value = data.get("binary_score")
        return isinstance(value, str)
    return False


def _coerce_content_to_text(content: Any) -> Optional[str]:
    """Normalize the assistant content field into plain text."""

    if content is None:
        return None

    if isinstance(content, str):
        if _looks_like_binary_score(content):
            return None
        return _strip_binary_score_fragment(content)

    if isinstance(content, list):
        segments: List[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            item_type = item.get("type")
            if item_type == "text" and isinstance(item.get("text"), str):
                segments.append(item["text"])
            elif item_type == "tool_result":
                # Ignore tool results for UI display by default.
                continue
        if segments:
            return "\n".join(segment.strip() for segment in segments if segment.strip())
        return None

    if isinstance(content, dict):
        # Some providers embed text under a "text" key.
        text = content.get("text")
        if isinstance(text, str) and not _looks_like_binary_score(text):
            return _strip_binary_score_fragment(text)
    return None


_BINARY_SCORE_RE = re.compile(r"\{\s*\"binary_score\"\s*:\s*\"(?:yes|no)\"\s*\}")


def _strip_binary_score_fragment(text: str) -> str:
    """Remove inline binary score markers from plain text."""

    cleaned = _BINARY_SCORE_RE.sub("", text)
    # Remove empty lines created by stripping and normalize spacing.
    return "\n".join(line for line in (line.strip() for line in cleaned.splitlines()) if line)

app = FastAPI(title="Assistant Chat API", version="1.0.0")

# Allow local development front-ends.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatPayload(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    user: str | None = Field(default=None, max_length=128)
    thread_id: str | None = Field(default=None, max_length=128, description="UUID for session management, used by mouth_v2 agent")
    agent: AgentName | None = Field(default=DEFAULT_AGENT)
    debug_mode: bool = Field(default=True, alias="debug")

    if PYDANTIC_V2:
        model_config = ConfigDict(populate_by_name=True)  # type: ignore[assignment]
    else:
        class Config:  # type: ignore[too-many-nested-blocks]
            allow_population_by_field_name = True


class WeChatLoginPayload(BaseModel):
    code: str = Field(..., min_length=1, max_length=256)


class RegisterPayload(BaseModel):
    id_card_last4: str = Field(..., min_length=4, max_length=4)
    phone_last4: str = Field(..., min_length=4, max_length=4)
    password: str = Field(..., min_length=8, max_length=128)
    password_confirmation: str = Field(..., min_length=8, max_length=128)
    privacy_consent: bool


class RegisterResult(BaseModel):
    login_code: str


class PatientLoginPayload(BaseModel):
    login_code: str
    password: str


class ChatOption(BaseModel):
    key: str
    label: str
    image_url: str | None = None


class OptionsConfig(BaseModel):
    """Configuration for options display and selection behavior."""
    multi_select: bool = False
    max_select: int | None = None
    confirm_button_text: str = "确认选择"


class ChatResult(BaseModel):
    reply: str
    raw_response: Any
    elapsed_time: float
    agent: AgentName
    options: List[ChatOption] | None = None
    options_config: OptionsConfig | None = None
    debug_info: Dict[str, Any] | None = None
    slot_update: Dict[str, Any] | None = None
    triage_result: Dict[str, Any] | None = None
    video_url: str | None = None
    video_password: str | None = None


class PresetQuestionsResult(BaseModel):
    questions: List[str]


def _build_client(agent: AgentName | None) -> ChatClient:
    profile = get_agent_profile(agent)
    base_url = profile.get("base_url", DEFAULT_BASE_URL)
    api_key = profile.get("api_key", "")
    if not api_key or api_key.startswith("replace-with"):
        raise HTTPException(status_code=503, detail="Agent API Key 未配置")
    print(f"[_build_client] agent={agent} base_url={base_url}")
    return ChatClient(base_url=base_url, api_key=api_key)


def _build_agent_identity(current_user: User, thread_id: str | None) -> tuple[str, str]:
    """Build Server-owned Agent identity fields from the authenticated user."""

    client_thread_id = thread_id or str(uuid.uuid4())
    try:
        normalized_thread_id = str(uuid.UUID(client_thread_id))
    except (ValueError, AttributeError) as exc:
        raise HTTPException(status_code=422, detail="thread_id 必须是有效的 UUID") from exc

    agent_user = f"mp:{current_user.id}"
    return agent_user, f"{agent_user}:{normalized_thread_id}"


def _load_preset_questions(agent: AgentName) -> List[str]:
    file_path = PRESET_FILES.get(agent)
    if not file_path or not file_path.exists():
        raise FileNotFoundError(f"Preset file not found for agent {agent.value}")

    with file_path.open("r", encoding="utf-8") as handle:
        return [line.strip() for line in handle if line.strip()]


def _extract_message_options(response: Any) -> tuple[List[ChatOption] | None, OptionsConfig | None]:
    """Extract options and configuration from the agent response.

    Returns:
        A tuple of (options_list, options_config). Both can be None if not present.
    """
    if not isinstance(response, dict):
        return None, None

    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        return None, None

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        return None, None

    message = first_choice.get("message")
    if not isinstance(message, dict):
        return None, None

    additional_kwargs = message.get("additional_kwargs")
    if not isinstance(additional_kwargs, dict):
        return None, None

    raw_options = additional_kwargs.get("options")
    if not isinstance(raw_options, list) or not raw_options:
        return None, None

    normalized: List[ChatOption] = []
    for candidate in raw_options:
        if not isinstance(candidate, dict):
            continue
        key = candidate.get("key")
        label = candidate.get("label")
        if not isinstance(key, str) or not isinstance(label, str):
            continue
        image_url_value = candidate.get("image_url")
        image_url: str | None
        if isinstance(image_url_value, str) and image_url_value.strip():
            image_url = image_url_value.strip()
        else:
            image_url = None
        normalized.append(ChatOption(key=key, label=label, image_url=image_url))

    if not normalized:
        return None, None

    # Extract options configuration (multi_select, max_select, confirm_button_text)
    multi_select = additional_kwargs.get("multi_select")
    max_select = additional_kwargs.get("max_select")
    confirm_button_text = additional_kwargs.get("confirm_button_text")

    options_config = OptionsConfig(
        multi_select=bool(multi_select) if multi_select is not None else False,
        max_select=int(max_select) if isinstance(max_select, (int, float)) and max_select > 0 else None,
        confirm_button_text=str(confirm_button_text).strip() if confirm_button_text else "确认选择",
    )

    return normalized, options_config


def _extract_debug_info(response: Any) -> Dict[str, Any] | None:
    if not isinstance(response, dict):
        return None
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        return None
    message = first_choice.get("message")
    if not isinstance(message, dict):
        return None
    additional_kwargs = message.get("additional_kwargs")
    if isinstance(additional_kwargs, dict):
        return additional_kwargs.get("debug_info")
    return None


def _extract_slot_update(response: Any) -> Dict[str, Any] | None:
    """Extract slot_update from additional_kwargs for mouth cavity agent."""
    if not isinstance(response, dict):
        return None
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        return None
    message = first_choice.get("message")
    if not isinstance(message, dict):
        return None
    additional_kwargs = message.get("additional_kwargs")
    if isinstance(additional_kwargs, dict):
        return additional_kwargs.get("slot_update")
    return None


def _extract_triage_result(response: Any) -> Dict[str, Any] | None:
    """Extract triage_result from additional_kwargs for mouth cavity agent."""
    if not isinstance(response, dict):
        return None
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        return None
    message = first_choice.get("message")
    if not isinstance(message, dict):
        return None
    additional_kwargs = message.get("additional_kwargs")
    if isinstance(additional_kwargs, dict):
        return additional_kwargs.get("triage_result")
    return None


def _extract_video_info(response: Any) -> tuple[str | None, str | None]:
    """Extract video_url and video_password from additional_kwargs."""
    if not isinstance(response, dict):
        return None, None
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        return None, None
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        return None, None
    message = first_choice.get("message")
    if not isinstance(message, dict):
        return None, None
    additional_kwargs = message.get("additional_kwargs")
    if isinstance(additional_kwargs, dict):
        return additional_kwargs.get("video_url"), additional_kwargs.get("video_password")
    return None, None


def _build_chat_result_or_raise(
    response: Any,
    elapsed: float,
    agent: AgentName,
) -> ChatResult:
    if response is None:
        raise HTTPException(status_code=502, detail="Chat service request failed")

    options, options_config = _extract_message_options(response)
    debug_info = _extract_debug_info(response)
    slot_update = _extract_slot_update(response)
    slot_update = _extract_slot_update(response)
    triage_result = _extract_triage_result(response)
    video_url, video_password = _extract_video_info(response)

    reply_text = ""
    if isinstance(response, dict):
        choices = response.get("choices", [])
        if isinstance(choices, list) and choices:
            for choice in choices:
                if not isinstance(choice, dict):
                    continue
                message = choice.get("message", {})
                if not isinstance(message, dict):
                    continue
                content = message.get("content")
                reply_text = _coerce_content_to_text(content)
                if reply_text:
                    break
            else:
                reply_text = ""
        if not reply_text:
            fallback_content = (
                response.get("content")
                or response.get("message")
                or response.get("answer")
                or response.get("output_text")
                or ""
            )
            reply_text = _coerce_content_to_text(fallback_content) or ""
    elif isinstance(response, str):
        reply_text = _coerce_content_to_text(response) or ""
    elif isinstance(response, list) and response:
        first = response[0]
        if isinstance(first, str):
            reply_text = _coerce_content_to_text(first) or ""
        elif isinstance(first, dict):
            reply_text = _coerce_content_to_text(
                first.get("content") or first.get("message")
            ) or ""

    if not reply_text:
        reply_text = "(No response content returned from agent.)"

    return ChatResult(
        reply=reply_text,
        raw_response=response,
        elapsed_time=elapsed,
        agent=agent,
        options=options,
        options_config=options_config,
        debug_info=debug_info,
        slot_update=slot_update,
        triage_result=triage_result,
        video_url=video_url,
        video_password=video_password,
    )


@app.post("/api/chat", response_model=ChatResult)
def create_chat(
    payload: ChatPayload,
    current_user: User = Depends(get_current_user),
) -> ChatResult:
    agent = payload.agent or DEFAULT_AGENT
    client = _build_client(agent)
    agent_user, agent_thread = _build_agent_identity(current_user, payload.thread_id)
    debug_provided = bool({"debug_mode", "debug"} & payload.__fields_set__)
    print(
        f"[api/chat] agent={agent.value} user={agent_user} thread_id={agent_thread} debug_mode={payload.debug_mode} provided={debug_provided}"
    )
    response, elapsed = client.simple_chat(
        content=payload.message,
        user=agent_user,
        debug_mode=payload.debug_mode,
        thread_id=agent_thread,
    )

    return _build_chat_result_or_raise(response, elapsed, agent)


class ReassessPayload(ChatPayload):
    reset_state: bool = Field(default=True)


@app.post("/api/chat/reassess", response_model=ChatResult)
def reassess_chat(
    payload: ReassessPayload,
    current_user: User = Depends(get_current_user),
) -> ChatResult:
    agent = payload.agent or DEFAULT_AGENT
    if agent not in (AgentName.MOUTH, AgentName.MOUTH_V2):
        raise HTTPException(status_code=400, detail="Reassessment only supported for mouth agents")

    client = _build_client(agent)
    agent_user, agent_thread = _build_agent_identity(current_user, payload.thread_id)
    debug_provided = bool({"debug_mode", "debug"} & payload.__fields_set__)
    print(
        f"[api/chat/reassess] agent={agent.value} user={agent_user} thread_id={agent_thread} debug_mode={payload.debug_mode} provided={debug_provided}"
    )
    messages = [
        {"role": "user", "content": payload.message},
        {"role": "user", "content": ""},
    ]
    response, elapsed = client.chat_completion(
        messages=messages,
        user=agent_user,
        reset_state=payload.reset_state,
        debug_mode=payload.debug_mode,
        thread_id=agent_thread,
    )

    return _build_chat_result_or_raise(response, elapsed, agent)


@app.get("/api/presets/{agent}", response_model=PresetQuestionsResult)
def get_preset_questions(
    agent: AgentName,
    current_user: User = Depends(get_current_user),
) -> PresetQuestionsResult:
    try:
        questions = _load_preset_questions(agent)
    except FileNotFoundError as exc:  # pragma: no cover - defensive guard
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OSError as exc:  # pragma: no cover - unlikely but handled explicitly
        raise HTTPException(status_code=500, detail="Failed to load preset questions") from exc

    return PresetQuestionsResult(questions=questions)


# ==================== Authentication Endpoints ====================


@app.post("/api/auth/register", response_model=RegisterResult, status_code=201)
def register_patient(payload: RegisterPayload, db: Session = Depends(get_db)) -> RegisterResult:
    """Create a password-backed platform patient identity."""

    if not re.fullmatch(r"[0-9]{4}", payload.id_card_last4) or not re.fullmatch(
        r"[0-9]{4}", payload.phone_last4
    ):
        raise HTTPException(status_code=422, detail="两组信息都必须是四位数字")
    if payload.password != payload.password_confirmation:
        raise HTTPException(status_code=422, detail="两次输入的密码不一致")
    if len(payload.password.encode("utf-8")) > 72:
        raise HTTPException(status_code=422, detail="密码过长，请控制在 72 字节以内")
    if not payload.privacy_consent:
        raise HTTPException(status_code=422, detail="请先阅读并同意隐私政策和医疗资料处理说明")

    try:
        patient = UserRepository(db).create_patient_account(
            id_card_last4=payload.id_card_last4,
            phone_last4=payload.phone_last4,
            password=payload.password,
        )
    except DuplicateLoginCodeError as exc:
        raise HTTPException(
            status_code=409, detail="该信息已注册，如非本人操作请联系医院。"
        ) from exc
    return RegisterResult(login_code=patient.login_code)


@app.post("/api/auth/login", response_model=Token)
def patient_login(payload: PatientLoginPayload, db: Session = Depends(get_db)) -> Token:
    """Issue a Server JWT for a patient login code and password."""

    invalid = HTTPException(status_code=401, detail="账号或密码错误")
    if not re.fullmatch(r"[0-9]{8}", payload.login_code):
        raise invalid
    repository = UserRepository(db)
    patient = repository.get_patient_by_login_code(payload.login_code)
    if patient is None or not verify_password(payload.password, patient.password_hash):
        raise invalid
    if patient.status != USER_STATUS_ACTIVE or patient.user.status != USER_STATUS_ACTIVE:
        raise invalid

    repository.record_patient_login(patient)
    return Token(
        access_token=create_access_token(patient.id, auth_method="patient"),
        user=TokenUser(id=patient.id, login_type="patient"),
    )


@app.post("/api/auth/wechat", response_model=Token)
def wechat_login(login_data: WeChatLoginPayload, db: Session = Depends(get_db)) -> Token:
    """Exchange a Mini Program code for a Server user JWT."""

    if WECHAT_CLIENT is None:
        raise HTTPException(status_code=503, detail="微信登录尚未配置")

    try:
        wechat_session = WECHAT_CLIENT.code2session(login_data.code)
    except WeChatLoginError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    user = UserRepository(db).find_or_create_by_wechat_identity(
        appid=WECHAT_CLIENT.appid,
        openid=wechat_session.openid,
        unionid=wechat_session.unionid,
    )
    if user.status != USER_STATUS_ACTIVE:
        raise HTTPException(status_code=403, detail="用户已被禁用")

    return Token(
        access_token=create_access_token(user.id),
        user=TokenUser(id=user.id),
    )


@app.get("/api/auth/me")
def get_me(current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """Get current authenticated user info."""
    return {
        "id": current_user.id,
        "login_type": current_user.login_type,
    }


@app.get("/health")
def health_check(db: Session = Depends(get_db)) -> Dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="0.0.0.0", port=8001, reload=True)
