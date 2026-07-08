# rag/vector_store/bm25_index.py
from __future__ import annotations
from typing import Any
"""
BM25 关键词检索索引

和 FaissStore 公用一份documents 列表
    documents[i] = {"id", "title", "content", "text"(可选)}

BM25 擅长：精确词、专业术语（如医院联网、Rh阴性）
向量检索擅长：语义相近但用词不同的问题

两者后面由 hybrid_search 合并
"""


def tokenize_chinese(text: str) -> list[str]:
    """
    中文分词。BM25 需要【词列表】，不能直接喂整句字符串
    例：“Rh阴性献血者要求” -> ["Rh", "阴性", "献血者", "要求"]
    """
    import jieba
    # jieba 会加载词典，第一次稍慢，属正常现象
    return [tok.strip() for tok in jieba.lcut(text) if tok.strip()]

def _doc_to_text(doc: dict[str, Any]) -> str:
    """
    把一条chunk转成BM25 可索引的文本
    标题权重通常更高，所以标题重复写一次（简单有效）
    """
    title = doc.get("title", "")
    content = doc.get("content", "")
    # 若FaissStore 有text字段，优先用
    if doc.get("text"):
        return doc["text"]
    return f"{title} {title} {content}"

class Bm25Index:
    """基于 rank_bm25 的关键词索引器 """

    def __init__(self) -> None:
        # 与FaisssStore.documents 保持同序，同长度
        self.documents: list[dict[str, Any]] = []
        self._tokenized_corpus: list[list[str]] = []
        self._bm25 = None  # BM25Okapi 实例，build 后才有值

    def build(self, documents: list[dict[str, Any]]) -> None:
        """
        根据documents 构建 BM25 索引
        在FaissStore.add_documents 后调用
        """
        from rank_bm25 import BM25Okapi

        self.documents = documents
        self._tokenized_corpus = [tokenize_chinese(_doc_to_text(doc)) for doc in documents]
        
        # BM25Okapi 接收「已分词的文档列表」
        self._bm25 = BM25Okapi(self._tokenized_corpus)

    def search(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        """
        关键词检索。

        Returns:
            与FaissStore.search 类似的结果列表, 额外带：
            - _index: 在documents 里的下标（给混合索引用）
            - bm25_score: BM25 相关性得分
        """
        if not self.documents or self._bm25 is None:
            return []

        query_tokens = tokenize_chinese(query)
        if not query_tokens:
            return []

        # 对所有文档打分，scores[i] 对应documents[i] 的得分
        scores = self._bm25.get_scores(query_tokens)

        # 取分数最高的top_k 个下标(argsort 升序， 所以取末尾)
        ranked_indices = sorted(
            range(len(scores)),
            key=lambda i: scores[i],
            reverse=True,
        )[: min(top_k, len(scores))]

        results: list[dict[str, Any]] = []
        for idx in ranked_indices:
            score = scores[idx]
            if score <= 0:
                # BM25 分数 <= 0 说明query 和该文档几乎无词重叠，可跳过
                continue
            doc = self.documents[idx]
            results.append({
                "_index": idx,
                "id": doc.get("id"),
                "title": doc.get("title", ""),
                "content": doc.get("content", ""),
                "bm25_score": score,
                # 为了和FaissStore 输出格式接近， 也给一个0~1 的相关性得分
                "relevance_score": score / (score + 1.0),
            })
        return results 

    def load_from_corpus(
        self,
        documents: list[dict[str, Any]],
        tokenized_corpus: list[list[str]],
    ) -> None:
        """
        从分词语料加载 BM25 索引 跳过jieba
        """
        from rank_bm25 import BM25Okapi
        self.documents = documents
        self._tokenized_corpus = tokenized_corpus
        self._bm25 = BM25Okapi(self._tokenized_corpus)