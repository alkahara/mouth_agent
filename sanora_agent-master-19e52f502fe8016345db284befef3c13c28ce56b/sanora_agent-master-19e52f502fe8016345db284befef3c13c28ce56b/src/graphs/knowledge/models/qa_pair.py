"""Question-Answer Pair data models."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict


@dataclass(slots=True)
class QAPair:
    """问答对数据模型"""

    qa_id: str
    pack_id: str
    question: str
    answer: str
    session_id: str
    created_at: str
    updated_at: str
    quality_score: float = 0.0
    usage_count: int = 0
    status: str = "active"
    metadata: Dict[str, Any] = field(default_factory=dict)
    # 追责字段
    editor_id: int | None = None
    editor_name: str | None = None
    edited_at: str | None = None

    @classmethod
    def create(
        cls,
        pack_id: str,
        question: str,
        answer: str,
        session_id: str,
        metadata: Dict[str, Any] | None = None,
        editor_id: int | None = None,
        editor_name: str | None = None,
        edited_at: str | None = None,
    ) -> "QAPair":
        """创建新的问答对实例"""
        now = datetime.now().isoformat()
        return cls(
            qa_id=str(uuid.uuid4()),
            pack_id=pack_id,
            question=question,
            answer=answer,
            session_id=session_id,
            created_at=now,
            updated_at=now,
            quality_score=0.0,
            usage_count=0,
            status="active",
            metadata=metadata or {},
            editor_id=editor_id,
            editor_name=editor_name,
            edited_at=edited_at or now,
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "qa_id": self.qa_id,
            "pack_id": self.pack_id,
            "question": self.question,
            "answer": self.answer,
            "session_id": self.session_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "quality_score": self.quality_score,
            "usage_count": self.usage_count,
            "status": self.status,
            "metadata": self.metadata,
            "editor_id": self.editor_id,
            "editor_name": self.editor_name,
            "edited_at": self.edited_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QAPair":
        """从字典创建实例"""
        return cls(
            qa_id=data["qa_id"],
            pack_id=data["pack_id"],
            question=data["question"],
            answer=data["answer"],
            session_id=data["session_id"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            quality_score=data.get("quality_score", 0.0),
            usage_count=data.get("usage_count", 0),
            status=data.get("status", "active"),
            metadata=data.get("metadata", {}),
            editor_id=data.get("editor_id"),
            editor_name=data.get("editor_name"),
            edited_at=data.get("edited_at"),
        )


@dataclass
class QAPairsCollection:
    """问答对集合（对应 qa_pairs.json 文件结构）"""

    pack_id: str
    generated_at: str
    total_count: int
    qa_pairs: Dict[str, QAPair]

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式（用于 JSON 序列化）"""
        return {
            "pack_id": self.pack_id,
            "generated_at": self.generated_at,
            "total_count": self.total_count,
            "qa_pairs": {qa_id: qa.to_dict() for qa_id, qa in self.qa_pairs.items()},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QAPairsCollection":
        """从字典创建实例"""
        qa_pairs = {
            qa_id: QAPair.from_dict(qa_data)
            for qa_id, qa_data in data.get("qa_pairs", {}).items()
        }
        return cls(
            pack_id=data["pack_id"],
            generated_at=data["generated_at"],
            total_count=data.get("total_count", len(qa_pairs)),
            qa_pairs=qa_pairs,
        )

    @classmethod
    def create_empty(cls, pack_id: str) -> "QAPairsCollection":
        """创建空的问答对集合"""
        return cls(
            pack_id=pack_id,
            generated_at=datetime.now().isoformat(),
            total_count=0,
            qa_pairs={},
        )


__all__ = ["QAPair", "QAPairsCollection"]
