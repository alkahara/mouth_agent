"""混合文档和问答对检索器"""

from __future__ import annotations

import asyncio
from typing import Any, List, Optional

from langchain_core.documents import Document
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.retrievers import BaseRetriever
from langchain_community.vectorstores import FAISS


class HybridDocQARetriever(BaseRetriever):
    """
    混合检索器：同时从文档向量库和问答对向量库检索，并合并结果

    支持对问答对进行加权提升（基于 quality_score 和 usage_count）
    """

    doc_retriever: BaseRetriever
    """文档检索器"""

    qa_vectorstore: Optional[FAISS] = None
    """问答对向量库"""

    doc_k: int = 7
    """从文档库检索的数量"""

    qa_k: int = 3
    """从问答对库检索的数量"""

    qa_score_boost: float = 1.2
    """问答对得分加成系数"""

    qa_pair_template: Optional[str] = None
    """问答对格式化模板，支持 {question} 和 {answer} 占位符"""

    qa_threshold: float = 0.85
    """问答对高匹配阈值（相似度 >= 此值时，直接使用问答对）"""

    class Config:
        arbitrary_types_allowed = True

    def _get_relevant_documents(
        self, query: str, *, run_manager: Optional[CallbackManagerForRetrieverRun] = None
    ) -> List[Document]:
        """
        检索相关文档（带 threshold 策略）

        策略：
        - 问答对相似度 >= 0.85：直接使用问答对（高匹配）
        - 问答对相似度 < 0.85：问答对 + 文档库混合搜索

        Args:
            query: 查询文本
            run_manager: 回调管理器

        Returns:
            合并后的文档列表
        """
        all_docs = []
        use_doc_retriever = True  # 默认使用文档检索

        # 1. 从问答对库检索（优先检索以判断 threshold）
        if self.qa_vectorstore is not None:
            try:
                # 使用 similarity_search_with_score 获取相似度分数
                qa_results_with_scores = self.qa_vectorstore.similarity_search_with_score(
                    query, k=self.qa_k
                )

                if qa_results_with_scores:
                    # FAISS 返回的是距离（越小越好），需要转换为相似度
                    # 相似度 = 1 / (1 + distance) 或使用 max(0, 1 - distance) 
                    best_distance = qa_results_with_scores[0][1]
                    # 使用归一化相似度：1 / (1 + distance)
                    best_similarity = 1 / (1 + best_distance)
                    
                    print(f"问答对最佳匹配距离: {best_distance:.4f}, 相似度: {best_similarity:.4f}")

                    # 判断是否高匹配
                    if best_similarity >= self.qa_threshold:
                        print(f"🎯 问答对高匹配 (>= {self.qa_threshold})，跳过文档检索")
                        use_doc_retriever = False
                    else:
                        print(f"📚 问答对低匹配 (< {self.qa_threshold})，混合文档检索")

                # 处理问答对结果
                for doc, score in qa_results_with_scores:
                    similarity = 1 / (1 + score)
                    
                    # 将答案添加到 page_content
                    answer = doc.metadata.get("answer", "")
                    if answer:
                        if self.qa_pair_template:
                            doc.page_content = self.qa_pair_template.format(
                                question=doc.page_content,
                                answer=answer
                            )
                        else:
                            doc.page_content = f"""=== 📌 精准问答对（请优先使用此答案）===
问题：{doc.page_content}
答案：
{answer}
=== 问答对结束 ==="""

                    # 添加元数据
                    doc.metadata["is_qa_pair"] = True
                    doc.metadata["similarity_score"] = similarity
                    doc.metadata["score_boost"] = self.qa_score_boost

                    # 计算额外加成
                    quality_score = doc.metadata.get("quality_score", 0.0)
                    usage_count = doc.metadata.get("usage_count", 0)
                    quality_boost = quality_score * 0.1
                    usage_boost = min(usage_count / 100, 0.1)
                    total_boost = self.qa_score_boost + quality_boost + usage_boost
                    doc.metadata["final_score_boost"] = total_boost

                    all_docs.append(doc)

            except Exception as e:
                print(f"问答对检索失败: {e}")

        # 2. 从文档库检索（根据 threshold 判断是否执行）
        if use_doc_retriever:
            try:
                # 动态调整文档检索数量：如果问答对不足，增加文档数量
                qa_count = len([d for d in all_docs if d.metadata.get("is_qa_pair")])
                target_total = self.doc_k + self.qa_k  # 目标总数 = 7 + 3 = 10
                actual_doc_k = target_total - qa_count  # 文档数量 = 总数 - 已有问答对数
                actual_doc_k = max(actual_doc_k, self.doc_k)  # 至少为 doc_k
                
                if hasattr(self.doc_retriever, "invoke"):
                    doc_results = self.doc_retriever.invoke(
                        query, config={"callbacks": run_manager.get_child()} if run_manager else None
                    )
                else:
                    doc_results = self.doc_retriever.get_relevant_documents(
                        query, callbacks=run_manager.get_child() if run_manager else None
                    )
                # 限制文档数量
                doc_results = doc_results[: actual_doc_k]
                all_docs.extend(doc_results)
            except Exception as e:
                print(f"文档检索失败: {e}")

        return all_docs

    async def _aget_relevant_documents(
        self, query: str, *, run_manager: Optional[CallbackManagerForRetrieverRun] = None
    ) -> List[Document]:
        """异步检索（带 threshold 策略）"""
        all_docs = []
        use_doc_retriever = True  # 默认使用文档检索

        # 1. 从问答对库检索（优先检索以判断 threshold）
        if self.qa_vectorstore is not None:
            try:
                # 使用 similarity_search_with_score 获取相似度分数
                qa_results_with_scores = await asyncio.to_thread(
                    self.qa_vectorstore.similarity_search_with_score, query, self.qa_k
                )

                if qa_results_with_scores:
                    best_distance = qa_results_with_scores[0][1]
                    best_similarity = 1 / (1 + best_distance)
                    
                    print(f"问答对最佳匹配距离: {best_distance:.4f}, 相似度: {best_similarity:.4f}")

                    if best_similarity >= self.qa_threshold:
                        print(f"🎯 问答对高匹配 (>= {self.qa_threshold})，跳过文档检索")
                        use_doc_retriever = False
                    else:
                        print(f"📚 问答对低匹配 (< {self.qa_threshold})，混合文档检索")

                # 处理问答对结果
                for doc, score in qa_results_with_scores:
                    similarity = 1 / (1 + score)
                    
                    answer = doc.metadata.get("answer", "")
                    if answer:
                        if self.qa_pair_template:
                            doc.page_content = self.qa_pair_template.format(
                                question=doc.page_content,
                                answer=answer
                            )
                        else:
                            doc.page_content = f"""=== 📌 精准问答对（请优先使用此答案）===
问题：{doc.page_content}
答案：
{answer}
=== 问答对结束 ==="""

                    doc.metadata["is_qa_pair"] = True
                    doc.metadata["similarity_score"] = similarity
                    doc.metadata["score_boost"] = self.qa_score_boost

                    quality_score = doc.metadata.get("quality_score", 0.0)
                    usage_count = doc.metadata.get("usage_count", 0)
                    quality_boost = quality_score * 0.1
                    usage_boost = min(usage_count / 100, 0.1)
                    total_boost = self.qa_score_boost + quality_boost + usage_boost
                    doc.metadata["final_score_boost"] = total_boost

                    all_docs.append(doc)

            except Exception as e:
                print(f"问答对检索失败: {e}")

        # 2. 从文档库异步检索（根据 threshold 判断是否执行）
        if use_doc_retriever:
            try:
                # 动态调整文档检索数量：如果问答对不足，增加文档数量
                qa_count = len([d for d in all_docs if d.metadata.get("is_qa_pair")])
                target_total = self.doc_k + self.qa_k
                actual_doc_k = target_total - qa_count
                actual_doc_k = max(actual_doc_k, self.doc_k)
                
                if hasattr(self.doc_retriever, "ainvoke"):
                    doc_results = await self.doc_retriever.ainvoke(
                        query, config={"callbacks": run_manager.get_child()} if run_manager else None
                    )
                elif hasattr(self.doc_retriever, "invoke"):
                    doc_results = await asyncio.to_thread(
                        self.doc_retriever.invoke, query
                    )
                else:
                    doc_results = await asyncio.to_thread(
                        self.doc_retriever.get_relevant_documents, query
                    )

                doc_results = doc_results[: actual_doc_k]
                all_docs.extend(doc_results)
            except Exception as e:
                print(f"文档检索失败: {e}")

        return all_docs


def create_hybrid_doc_qa_retriever(
    doc_retriever: BaseRetriever,
    qa_vectorstore: Optional[FAISS] = None,
    doc_k: int = 7,
    qa_k: int = 3,
    qa_score_boost: float = 1.2,
    qa_pair_template: Optional[str] = None,
    qa_threshold: float = 0.85,
) -> HybridDocQARetriever:
    """
    创建混合文档和问答对检索器

    检索策略：
    - 问答对相似度 >= threshold：直接使用问答对（高匹配）
    - 问答对相似度 < threshold：问答对 + 文档库混合搜索

    Args:
        doc_retriever: 文档检索器（可能已包含 BM25、重排序等）
        qa_vectorstore: 问答对向量库
        doc_k: 从文档库检索的数量
        qa_k: 从问答对库检索的数量
        qa_score_boost: 问答对得分加成系数
        qa_pair_template: 问答对格式化模板（支持 {question} 和 {answer} 占位符）
        qa_threshold: 问答对高匹配阈值（默认 0.85）

    Returns:
        混合检索器实例
    """
    return HybridDocQARetriever(
        doc_retriever=doc_retriever,
        qa_vectorstore=qa_vectorstore,
        doc_k=doc_k,
        qa_k=qa_k,
        qa_score_boost=qa_score_boost,
        qa_pair_template=qa_pair_template,
        qa_threshold=qa_threshold,
    )


__all__ = ["HybridDocQARetriever", "create_hybrid_doc_qa_retriever"]
