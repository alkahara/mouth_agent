"""Service layer wrapping the JSONL long-term memory store."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from .longterm_file_store import LongTermFileStore


class LongTermMemoryService:
    """Thin wrapper to simplify CRUD for the long-term memory store."""

    def __init__(self, file_path: Optional[str] = None, store: Optional[LongTermFileStore] = None):
        path = file_path or os.getenv("LONGTERM_MEMORY_PATH")
        self.store = store or LongTermFileStore(path)

    def remember(
        self,
        user_id: str,
        title: str,
        content: str,
        tags: Optional[List[str]] = None,
        source: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not user_id:
            raise ValueError("user_id is required")
        if not title:
            raise ValueError("title is required")
        if not content:
            raise ValueError("content is required")
        return self.store.add_entry(user_id=user_id, title=title, content=content, tags=tags, source=source)

    def update(
        self,
        user_id: str,
        entry_id: str,
        *,
        title: Optional[str] = None,
        content: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        if not user_id or not entry_id:
            raise ValueError("user_id and entry_id are required")
        updated = self.store.update_entry(entry_id=entry_id, user_id=user_id, title=title, content=content, tags=tags)
        if not updated:
            raise ValueError("entry not found")
        return updated

    def delete(self, user_id: str, entry_id: str) -> bool:
        if not user_id or not entry_id:
            raise ValueError("user_id and entry_id are required")
        ok = self.store.soft_delete(entry_id=entry_id, user_id=user_id)
        if not ok:
            raise ValueError("entry not found")
        return ok

    def search(self, user_id: str, query: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        if not user_id:
            raise ValueError("user_id is required")
        return self.store.search(user_id=user_id, query=query, limit=limit)
