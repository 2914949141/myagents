from sentence_transformers import CrossEncoder
import math

class Reranker:
    def __init__(self, model_name: str = "BAAI/bge-reranker-base"):
        self.model = CrossEncoder(model_name, device="cpu")

    @staticmethod
    def _to_relevance(logit: float) -> float:
        return 1.0 / (1.0 + math.exp(-float(logit)))

    def rerank(self, query: str, hits: list, top_k: int = 3) -> list:
        # hits 来自于 hybrid_search , 每条有title, content, _index
        pairs = [(query, f"{h['title']} {h['content']}") for h in hits]
        scores = self.model.predict(pairs)
        ranked = sorted(zip(hits, scores), key=lambda x: x[1], reverse=True)
        return [
            {
                **h, 
                "rerank_score": float(score),
                "relevance_score": self._to_relevance(score),
            } for h, score in ranked[:top_k]
        ]