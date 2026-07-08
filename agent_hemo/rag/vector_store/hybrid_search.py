# rag/vector_store/hybrid_search.py
"""
混合检索：向量召回 + BM25 召回 + RRF 融合 -> 最终 top_k

典型用法 (在 FaissStore 里)
    vector_hits = self._search_vector(query, recall_k)
    bm25_hits = self.bm25_index.search(query, recall_k)
    return hybrid_search(vector_hits, bm25_hits, documents, top_k)
"""

from __future__ import annotations
from typing import Any

def _hit_index(hit: dict[str, Any]) -> int | None:
    """
    从单条检索结果里取出documents 列表下标
    向量/BM25 召回结果里都带 _index 字段
    """
    idx = hit.get("_index")
    if idx is None:
        return None
    return int(idx)

def rrf_merge(
    ranked_lists: list[list[dict[str, Any]]],
    rrf_k: int = 60
) -> list[tuple[int, float]]:
    """
    多路检索结果的RRF 融合

    Args:
        ranked_lists: 每一路的检索结果（已按相关度排好序）
        rrf_k: RRF平滑常数, 常用 60
    
    Returns: 
        [(doc_index, rrf_score), ...] 按 rrf_score 降序
    """
    scores: dict[int, float] = {}

    for hits in ranked_lists:
        for rank, hit in enumerate(hits):
            idx = _hit_index(hit)
            if idx is None:
                continue
            # rank 从0开始， 所以 +1
            scores[idx] = scores.get(idx, 0.0) + 1.0 / (rrf_k + rank + 1)
    # 按 rrf_score 降序
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)

def hybrid_search(
    vector_hits: list[dict[str, Any]],
    bm25_hits: list[dict[str, Any]],
    documents: list[dict[str, Any]],
    top_k: int = 3,
    rrf_k: int = 60
) -> list[dict[str, Any]]:
    """
    合并向量 + BM25 两路结果，返回最终 top_k。

    Args:
        vector_hits: FaissStore 向量检索结果（每条含 _index）
        bm25_hits:   Bm25Index 检索结果（每条含 _index）
        documents:   完整文档列表（FaissStore.documents）
        top_k:       最终返回条数（给 LLM 用，通常 3）
        rrf_k:       RRF 参数
    Returns:
        与 FaissStore.search 兼容的结果列表
    """
    if not documents:
        return []

    merged = rrf_merge([vector_hits, bm25_hits], rrf_k=rrf_k)

    results: list[dict[str, Any]] = []
    for idx, rrf_score in merged[:top_k]:
        doc = documents[idx]
        results.append({
            "_index": idx,
            "id": doc.get("id"),
            "title": doc.get("title", ""),
            "content": doc.get("content", ""),
            "rrf_score": rrf_score,
            # rag_tool.py 会读 relevance_score 做展示，这里用 rrf 分数映射一下
            "relevance_score": rrf_score,  # 也可改成 min(rrf_score * 10, 1.0)
        })
    return results