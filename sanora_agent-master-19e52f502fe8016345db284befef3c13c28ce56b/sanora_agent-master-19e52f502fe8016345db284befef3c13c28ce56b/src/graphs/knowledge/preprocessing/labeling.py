"""Utilities for applying metadata labels to documents."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List


def load_label_mapping(directory: Path) -> Dict[str, List[str]]:
    """Read ``labels.json`` under ``directory`` if present."""
    labels_file = directory / "labels.json"
    if not labels_file.exists():
        return {}
    try:
        raw = json.loads(labels_file.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"警告：无法读取 {labels_file.name}，忽略标签设置：{exc}")
        return {}

    mapping: Dict[str, List[str]] = {}
    if isinstance(raw, dict):
        for key, value in raw.items():
            key_str = str(key).strip()
            if not key_str:
                continue
            if isinstance(value, (list, tuple)):
                labels = [str(item).strip() for item in value if str(item).strip()]
            elif value is None:
                labels = []
            else:
                label = str(value).strip()
                labels = [label] if label else []
            if labels:
                mapping[key_str] = labels
    return mapping


def merge_labels(existing: List[str] | None, extra: List[str]) -> List[str]:
    """Merge label lists while preserving order and uniqueness."""
    merged: List[str] = []
    if existing:
        merged.extend(str(item).strip() for item in existing if str(item).strip())
    for label in extra:
        if label not in merged:
            merged.append(label)
    return merged


__all__ = ["load_label_mapping", "merge_labels"]
