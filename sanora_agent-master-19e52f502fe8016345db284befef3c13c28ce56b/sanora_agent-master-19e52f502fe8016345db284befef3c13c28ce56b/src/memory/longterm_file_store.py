"""Simple JSONL-based long-term memory store (file only, no DB)."""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


def _utc_now() -> str:
    """Return an ISO timestamp with Z suffix."""
    return datetime.now(timezone.utc).isoformat()


def _default_store_path() -> Path:
    """Default path: repo/.data/longterm_memory.jsonl."""
    base = Path(__file__).resolve().parents[3]  # repo root (system)
    return base / ".data" / "longterm_memory.jsonl"


class LongTermFileStore:
    """File-backed store using JSONL with in-memory rewrite for edits."""

    def __init__(self, file_path: Optional[str | Path] = None):
        self.file_path = Path(file_path) if file_path else _default_store_path()
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        if not self.file_path.exists():
            self.file_path.touch()

    # ----- helpers -----
    def _read_entries(self) -> List[Dict[str, Any]]:
        entries: List[Dict[str, Any]] = []
        if not self.file_path.exists():
            return entries

        with self.file_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        entries.append(obj)
                except json.JSONDecodeError:
                    # Skip malformed lines to keep robustness
                    continue
        return entries

    def _write_entries(self, entries: Iterable[Dict[str, Any]]) -> None:
        with self.file_path.open("w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # ----- CRUD -----
    def add_entry(
        self,
        user_id: str,
        title: str,
        content: str,
        tags: Optional[List[str]] = None,
        source: Optional[str] = None,
    ) -> Dict[str, Any]:
        now = _utc_now()
        entry = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "title": title,
            "content": content,
            "tags": tags or [],
            "source": source or "",
            "created_at": now,
            "updated_at": now,
            "last_used_at": now,
            "deleted": False,
        }
        with self._lock:
            entries = self._read_entries()
            entries.append(entry)
            self._write_entries(entries)
        return entry

    def update_entry(
        self,
        entry_id: str,
        user_id: str,
        *,
        title: Optional[str] = None,
        content: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        with self._lock:
            entries = self._read_entries()
            updated_entry = None
            for entry in entries:
                if entry.get("id") == entry_id and entry.get("user_id") == user_id and not entry.get("deleted"):
                    if title is not None:
                        entry["title"] = title
                    if content is not None:
                        entry["content"] = content
                    if tags is not None:
                        entry["tags"] = tags
                    entry["updated_at"] = _utc_now()
                    updated_entry = entry.copy()
                    break
            if updated_entry:
                self._write_entries(entries)
            return updated_entry

    def soft_delete(self, entry_id: str, user_id: str) -> bool:
        with self._lock:
            entries = self._read_entries()
            changed = False
            for entry in entries:
                if entry.get("id") == entry_id and entry.get("user_id") == user_id and not entry.get("deleted"):
                    entry["deleted"] = True
                    entry["updated_at"] = _utc_now()
                    changed = True
                    break
            if changed:
                self._write_entries(entries)
            return changed

    def get_by_id(self, entry_id: str, user_id: str, include_deleted: bool = False) -> Optional[Dict[str, Any]]:
        entries = self._read_entries()
        for entry in entries:
            if entry.get("id") == entry_id and entry.get("user_id") == user_id:
                if not include_deleted and entry.get("deleted"):
                    return None
                return entry.copy()
        return None

    # ----- Query helpers -----
    def list_recent(
        self, user_id: str, limit: int = 5, include_deleted: bool = False
    ) -> List[Dict[str, Any]]:
        entries = [
            e
            for e in self._read_entries()
            if e.get("user_id") == user_id and (include_deleted or not e.get("deleted"))
        ]
        entries.sort(key=lambda e: e.get("updated_at") or e.get("created_at", ""), reverse=True)
        return [e.copy() for e in entries[:limit]]

    def search(self, user_id: str, query: Optional[str], limit: int = 5) -> List[Dict[str, Any]]:
        if not query:
            return self.list_recent(user_id, limit=limit)

        q = query.lower().strip()
        with self._lock:
            entries = self._read_entries()
            hits: List[Dict[str, Any]] = []
            touched = False
            now = _utc_now()
            for entry in entries:
                if entry.get("user_id") != user_id or entry.get("deleted"):
                    continue
                haystack = " ".join(
                    [
                        str(entry.get("title", "")),
                        str(entry.get("content", "")),
                        " ".join(entry.get("tags", []) or []),
                    ]
                ).lower()
                if q in haystack:
                    entry["last_used_at"] = now
                    hits.append(entry.copy())
                    touched = True
            # Sort by last_used_at then updated_at
            hits.sort(
                key=lambda e: (e.get("last_used_at") or e.get("updated_at") or e.get("created_at", "")),
                reverse=True,
            )
            if touched:
                self._write_entries(entries)
            return hits[:limit]
