"""RAG 检索层评测: Hit@K、MRR, 对比 hybrid / vector / bm25。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
QUESTIONS_FILE = EVAL_DIR / "questions.jsonl"

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agent_hemo.rag.vector_store.faiss_store import FaissStore

def load_questions() -> list[dict]:
    rows = []
    with QUESTIONS_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows

def hit_at_k(results: list[dict], expected_in_title: str, k: int) -> bool:
    for r in results[:k]:
        if expected_in_title in r.get("title", ""):
            return True
    return False

def reciprocal_rank(results: list[dict], expected_in_title: str) -> float:
    for i, r in enumerate(results, start=1):
        if expected_in_title in r.get("title", ""):
            return 1.0 / i
    return 0.0

def evaluate_channel(name: str, search_fn, questions: list[dict], k: int = 3) -> dict:
    hits = []
    rrs = []
    for q in questions:
        results = search_fn(q["query"])
        hit = hit_at_k(results, q["expected_in_title"], k)
        hits.append(hit)
        rrs.append(reciprocal_rank(results, q["expected_in_title"]))
        mark = "OK" if hit else "MISS"
        top_titles = [r["title"] for r in results[:k]]
        print(f" [{mark}] {q['query']}")
        print(f"      期望 title 含: {q['expected_in_title']}")
        print(f"      Top-{k}: {(top_titles)}")

    n = len(questions)
    return {
        "channel": name,
        f"hit@{k}": sum(hits) / n if n else 0.0,
        "mrr": sum(rrs) / n if n else 0.0,
    }

def main() -> None:
    questions = load_questions()
    print(f"加载 {len(questions)} 道检索题\n")
    print("初始化 FaissStore（manifest 变化时会自动重建）...\n")
    store = FaissStore()
    print(f"索引块数: {store.get_document_count()}\n")

    k = 3
    channels = [
        ("hybrid+rerank", lambda q: store.search(q, top_k=k)),
        ("vector", lambda q: store._search_vector(q, top_k=k)),
        ("bm25", lambda q: store.bm25_index.search(q, top_k=k)),
    ]

    summary = []
    for name, fn in channels:
        print(f"=== {name} ===")
        stats = evaluate_channel(name, fn, questions, k)
        summary.append(stats)
        print(f"  Hit@{k}: {stats[f'hit@{k}']:.1%}  MRR: {stats['mrr']:.3f}\n")

    print("=== 汇总 ===")
    for s in summary:
        print(f"{s['channel']:16} Hit@{k}={s[f'hit@{k}']:.1%}  MRR={s['mrr']:.3f}")

if __name__ == "__main__":
    main()