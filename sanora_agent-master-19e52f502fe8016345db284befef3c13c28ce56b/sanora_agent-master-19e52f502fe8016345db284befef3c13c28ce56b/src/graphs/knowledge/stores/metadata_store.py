"""切片元数据存储管理"""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

from ..preprocessing.enhanced_splitter import DocumentChunks


def save_chunks_metadata(
    pack_id: str,
    document_chunks_list: List[DocumentChunks],
    chunk_size: int,
    chunk_overlap: int,
    output_path: Path,
) -> None:
    """
    保存切片元数据到 JSON 文件

    Args:
        pack_id: 知识包 ID
        document_chunks_list: 文档切片列表
        chunk_size: 切片大小
        chunk_overlap: 重叠大小
        output_path: 输出文件路径（chunks_metadata.json）

    生成的 JSON 格式：
    {
      "pack_id": "sheld_qa",
      "generated_at": "2025-11-13T10:30:00",
      "chunking_config": {...},
      "documents": {
        "file1.pdf": {
          "file_path": "/path/to/file1.pdf",
          "total_chars": 12450,
          "total_chunks": 15,
          "processed_at": "2025-11-13T10:30:00",
          "chunks": [...]
        }
      }
    }
    """
    data = {
        "pack_id": pack_id,
        "generated_at": datetime.now().isoformat(),
        "chunking_config": {
            "segmentation_rule": "自定义",
            "chunk_size": chunk_size,
            "overlap": chunk_overlap,
            "separator": "\\n\\n",
        },
        "documents": {}
    }

    for doc_chunks in document_chunks_list:
        data["documents"][doc_chunks.file_name] = {
            "file_path": doc_chunks.file_path,
            "total_chars": doc_chunks.total_chars,
            "total_chunks": len(doc_chunks.chunks),
            "processed_at": datetime.now().isoformat(),
            "chunks": [
                {
                    "chunk_id": chunk.chunk_id,
                    "sequence": chunk.sequence,
                    "content": chunk.content,
                    "char_count": chunk.char_count,
                    "start_pos": chunk.start_pos,
                    "end_pos": chunk.end_pos,
                    "metadata": chunk.metadata,
                    "page_mapping": chunk.page_mapping,  # 页码映射（兼容 parent page）
                }
                for chunk in doc_chunks.chunks
            ]
        }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def load_chunks_metadata(metadata_path: Path) -> Dict[str, Any] | None:
    """
    加载切片元数据

    Args:
        metadata_path: 元数据文件路径

    Returns:
        元数据字典，如果文件不存在则返回 None
    """
    if not metadata_path.exists():
        return None

    with open(metadata_path, 'r', encoding='utf-8') as f:
        return json.load(f)


__all__ = ["save_chunks_metadata", "load_chunks_metadata"]
