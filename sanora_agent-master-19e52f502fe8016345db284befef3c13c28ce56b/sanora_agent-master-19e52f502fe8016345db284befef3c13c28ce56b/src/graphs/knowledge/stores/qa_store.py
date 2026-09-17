"""问答对存储管理"""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

from ..models.qa_pair import QAPair, QAPairsCollection


def load_qa_pairs(qa_pairs_path: Path) -> Optional[QAPairsCollection]:
    """
    加载问答对集合

    Args:
        qa_pairs_path: qa_pairs.json 文件路径

    Returns:
        QAPairsCollection 实例，如果文件不存在则返回 None
    """
    if not qa_pairs_path.exists():
        return None

    try:
        with open(qa_pairs_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return QAPairsCollection.from_dict(data)
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        print(f"加载问答对失败: {e}")
        return None


def save_qa_pairs(collection: QAPairsCollection, qa_pairs_path: Path) -> None:
    """
    保存问答对集合到文件

    Args:
        collection: 问答对集合
        qa_pairs_path: qa_pairs.json 文件路径
    """
    # 确保目录存在
    qa_pairs_path.parent.mkdir(parents=True, exist_ok=True)

    # 更新生成时间和总数
    collection.generated_at = datetime.now().isoformat()
    collection.total_count = len(collection.qa_pairs)

    # 写入文件
    with open(qa_pairs_path, "w", encoding="utf-8") as f:
        json.dump(collection.to_dict(), f, ensure_ascii=False, indent=2)


def add_qa_pair(
    pack_id: str,
    question: str,
    answer: str,
    session_id: str,
    qa_pairs_path: Path,
    metadata: Optional[Dict[str, Any]] = None,
    editor_id: Optional[int] = None,
    editor_name: Optional[str] = None,
    edited_at: Optional[str] = None,
) -> QAPair:
    """
    添加新的问答对（自动去重）

    如果存在相同问题的旧问答对，会删除旧的，保留新的。

    Args:
        pack_id: 知识包 ID
        question: 用户问题
        answer: 系统答案
        session_id: 来源会话 ID
        qa_pairs_path: qa_pairs.json 文件路径
        metadata: 额外元数据
        editor_id: 编辑人 ID（追责）
        editor_name: 编辑人用户名（追责）
        edited_at: 编辑时间（追责）

    Returns:
        新创建的 QAPair 实例
    """
    # 加载现有集合或创建新集合
    collection = load_qa_pairs(qa_pairs_path)
    if collection is None:
        collection = QAPairsCollection.create_empty(pack_id)

    # 🔧 去重：删除相同问题的旧问答对
    question_normalized = question.strip()
    duplicate_ids = [
        qa_id for qa_id, qa in collection.qa_pairs.items()
        if qa.question.strip() == question_normalized
    ]
    for dup_id in duplicate_ids:
        del collection.qa_pairs[dup_id]
        print(f"已删除重复问答对: {dup_id}")

    # 创建新问答对
    qa_pair = QAPair.create(
        pack_id=pack_id,
        question=question,
        answer=answer,
        session_id=session_id,
        metadata=metadata,
        editor_id=editor_id,
        editor_name=editor_name,
        edited_at=edited_at,
    )

    # 添加到集合
    collection.qa_pairs[qa_pair.qa_id] = qa_pair

    # 保存到文件
    save_qa_pairs(collection, qa_pairs_path)

    return qa_pair


def get_qa_pair(qa_id: str, qa_pairs_path: Path) -> Optional[QAPair]:
    """
    获取指定的问答对

    Args:
        qa_id: 问答对 ID
        qa_pairs_path: qa_pairs.json 文件路径

    Returns:
        QAPair 实例，如果不存在则返回 None
    """
    collection = load_qa_pairs(qa_pairs_path)
    if collection is None:
        return None

    return collection.qa_pairs.get(qa_id)


def get_active_qa_pairs(qa_pairs_path: Path) -> list[QAPair]:
    """
    获取所有活跃的问答对（status='active'）

    Args:
        qa_pairs_path: qa_pairs.json 文件路径

    Returns:
        活跃问答对列表
    """
    collection = load_qa_pairs(qa_pairs_path)
    if collection is None:
        return []

    return [
        qa_pair
        for qa_pair in collection.qa_pairs.values()
        if qa_pair.status == "active"
    ]


class QAPairStore:
    """问答对存储管理器（面向对象接口）"""

    def __init__(self, pack_id: str, cache_dir: Path):
        """
        初始化存储管理器

        Args:
            pack_id: 知识包 ID
            cache_dir: 缓存目录（通常是 vector_cache/）
        """
        self.pack_id = pack_id
        self.cache_dir = cache_dir
        self.qa_pairs_path = cache_dir / "qa_pairs.json"

    def add(
        self,
        question: str,
        answer: str,
        session_id: str,
        metadata: Optional[Dict[str, Any]] = None,
        editor_id: Optional[int] = None,
        editor_name: Optional[str] = None,
        edited_at: Optional[str] = None,
    ) -> QAPair:
        """添加新问答对"""
        return add_qa_pair(
            pack_id=self.pack_id,
            question=question,
            answer=answer,
            session_id=session_id,
            qa_pairs_path=self.qa_pairs_path,
            metadata=metadata,
            editor_id=editor_id,
            editor_name=editor_name,
            edited_at=edited_at,
        )

    def get(self, qa_id: str) -> Optional[QAPair]:
        """获取指定问答对"""
        return get_qa_pair(qa_id, self.qa_pairs_path)

    def get_active(self) -> list[QAPair]:
        """获取所有活跃问答对"""
        return get_active_qa_pairs(self.qa_pairs_path)

    def load_collection(self) -> Optional[QAPairsCollection]:
        """加载完整的问答对集合"""
        return load_qa_pairs(self.qa_pairs_path)

    @property
    def exists(self) -> bool:
        """检查问答对文件是否存在"""
        return self.qa_pairs_path.exists()


__all__ = [
    "QAPairStore",
    "load_qa_pairs",
    "save_qa_pairs",
    "add_qa_pair",
    "get_qa_pair",
    "get_active_qa_pairs",
]
