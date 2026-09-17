"""增强的文档切分器，记录切片位置信息并兼容 parent page 功能"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple
from pathlib import Path
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


@dataclass
class ChunkInfo:
    """单个切片的详细信息"""
    chunk_id: str
    sequence: int
    content: str
    char_count: int
    start_pos: int
    end_pos: int
    metadata: dict
    page_mapping: List[int] | None = None  # 切片跨越的页码列表


@dataclass
class DocumentChunks:
    """单个文档的所有切片"""
    file_name: str
    file_path: str
    total_chars: int
    chunks: List[ChunkInfo]


def split_documents_with_positions(
    documents: List[Document],
    *,
    chunk_size: int,
    chunk_overlap: int,
    pack_id: str,
) -> Tuple[List[Document], List[DocumentChunks]]:
    """
    切分文档并记录位置信息（支持 parent page）

    Args:
        documents: 待切分的文档列表
        chunk_size: 切片大小
        chunk_overlap: 重叠大小
        pack_id: 知识包 ID

    Returns:
        (langchain_documents, document_chunks_list)
        - langchain_documents: 用于向量化的标准 Document 对象
        - document_chunks_list: 包含位置信息的切片元数据

    工作原理：
    1. 按文件合并所有页面内容
    2. 记录每个页面的边界信息
    3. 切分合并后的文本
    4. 计算每个切片跨越的页码
    5. 单页切片自动添加 parent page 信息
    6. 跨页切片保持原样（不添加 parent page）
    """
    # 使用字符长度计算，避免 tiktoken 网络依赖
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
    )

    # 按源文件分组
    docs_by_source = {}
    for doc in documents:
        source = doc.metadata.get("source", "unknown")
        if source not in docs_by_source:
            docs_by_source[source] = []
        docs_by_source[source].append(doc)

    all_langchain_docs = []
    all_document_chunks = []

    # 逐文件处理
    for source, source_docs in docs_by_source.items():
        # 记录每个页面的边界信息
        page_boundaries = []
        current_offset = 0

        # 检测文档是否有页码信息
        has_page_info = any("page" in doc.metadata for doc in source_docs)

        full_text_parts = []
        for doc_idx, doc in enumerate(source_docs):
            page_content = doc.page_content
            # 如果文档没有页码信息（如 DOCX），使用虚拟页码 0
            # 如果有页码信息（如 PDF），使用真实页码
            if has_page_info:
                page_number = doc.metadata.get("page")
            else:
                page_number = 0  # 对于无页码文档，视为单页文档（页码0）

            # 记录页面边界
            page_boundaries.append({
                "page_number": page_number,
                "start": current_offset,
                "end": current_offset + len(page_content),
                "content": page_content,
            })

            full_text_parts.append(page_content)
            current_offset += len(page_content) + 2  # +2 for "\n\n"

        # 合并所有页面
        full_text = "\n\n".join(full_text_parts)
        total_chars = len(full_text)

        # 切分
        splits = splitter.split_text(full_text)

        chunks_info = []
        current_pos = 0

        for idx, split_content in enumerate(splits):
            # 查找在原文中的位置
            start_pos = full_text.find(split_content, current_pos)
            if start_pos == -1:
                start_pos = current_pos
            end_pos = start_pos + len(split_content)

            chunk_id = f"{source}::chunk-{idx}"

            # 计算切片跨越的页码
            page_mapping = []
            for page_info in page_boundaries:
                # 检查切片是否与该页有交集
                if not (end_pos <= page_info["start"] or start_pos >= page_info["end"]):
                    # 现在所有文档都有 page_number（包括 DOCX 的虚拟页码 0）
                    page_mapping.append(page_info["page_number"])

            # 创建 LangChain Document（用于向量化）
            chunk_metadata = {
                "source": source,
                "chunk_id": chunk_id,
                "chunk_sequence": idx + 1,
                "pack_id": pack_id,
            }

            # 如果切片只在单个页面内，添加 parent page 信息
            # 这样 ParentPageRetriever 会将 chunk 替换为整页内容
            if len(page_mapping) == 1:
                page_num = page_mapping[0]
                for page_info in page_boundaries:
                    if page_info["page_number"] == page_num:
                        chunk_metadata["parent_page_content"] = page_info["content"]
                        chunk_metadata["parent_page_number"] = page_num
                        chunk_metadata["parent_document_id"] = f"{source}::page={page_num}"
                        break
            # 跨页切片不添加 parent page 信息，保持 chunk 原样

            langchain_doc = Document(
                page_content=split_content,
                metadata=chunk_metadata
            )
            all_langchain_docs.append(langchain_doc)

            # 创建详细切片信息（用于前端展示）
            # 现在所有文档都应该有 page_mapping（PDF为真实页码，DOCX为虚拟页码[0]）
            chunk_info = ChunkInfo(
                chunk_id=chunk_id,
                sequence=idx + 1,
                content=split_content,
                char_count=len(split_content),
                start_pos=start_pos,
                end_pos=end_pos,
                metadata={
                    "source": source,
                    "page_mapping": page_mapping,
                },
                page_mapping=page_mapping,
            )
            chunks_info.append(chunk_info)

            current_pos = end_pos - chunk_overlap

        # 记录文档切片结果
        file_name = Path(source).name

        doc_chunks = DocumentChunks(
            file_name=file_name,
            file_path=source,
            total_chars=total_chars,
            chunks=chunks_info,
        )
        all_document_chunks.append(doc_chunks)

    return all_langchain_docs, all_document_chunks


__all__ = ["ChunkInfo", "DocumentChunks", "split_documents_with_positions"]
