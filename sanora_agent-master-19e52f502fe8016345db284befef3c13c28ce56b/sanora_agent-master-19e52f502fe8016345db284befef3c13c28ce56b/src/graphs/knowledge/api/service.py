"""知识库文档 API 服务"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Dict, Any

from ..base import KnowledgePackRegistry
from ..stores.metadata_store import load_chunks_metadata


class KnowledgeDocumentService:
    """知识库文档服务"""

    @staticmethod
    def get_document_chunks(pack_id: str, file_name: str) -> Optional[Dict[str, Any]]:
        """
        获取单个文档的切片信息

        Args:
            pack_id: 知识包 ID（如 "sheld_qa"）
            file_name: 文件名（如 "policy.pdf"）

        Returns:
            文档切片信息，格式符合 Sheld Server 期望：
            {
              "pack_id": "sheld_qa",
              "file_name": "policy.pdf",
              "document_info": {
                "total_chars": 12450,
                "total_chunks": 15,
                "processed_at": "2025-11-13T10:30:00"
              },
              "chunking_config": {
                "segmentation_rule": "自定义",
                "chunk_size": 800,
                "overlap": 80,
                "separator": "\\n\\n"
              },
              "chunks": [
                {
                  "chunk_id": "...",
                  "sequence": 1,
                  "content": "...",
                  "char_count": 800,
                  "start_pos": 0,
                  "end_pos": 800,
                  "metadata": {...},
                  "page_mapping": [1]
                },
                ...
              ]
            }
        """
        try:
            pack = KnowledgePackRegistry.create(pack_id)
            metadata_path = pack.embedding.cache_dir / "chunks_metadata.json"
            metadata = load_chunks_metadata(metadata_path)

            if not metadata:
                return None

            doc_data = metadata.get("documents", {}).get(file_name)
            if not doc_data:
                return None

            return {
                "pack_id": pack_id,
                "file_name": file_name,
                "document_info": {
                    "total_chars": doc_data["total_chars"],
                    "total_chunks": doc_data["total_chunks"],
                    "processed_at": doc_data["processed_at"],
                },
                "chunking_config": metadata["chunking_config"],
                "chunks": doc_data["chunks"],
            }
        except Exception:
            return None


# 全局实例
knowledge_doc_service = KnowledgeDocumentService()


__all__ = ["knowledge_doc_service"]
