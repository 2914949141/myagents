# 临时测试脚本 test_bm25.py

from agent_hemo.rag.vector_store.bm_index import Bm25Index
from agent_hemo.rag.vector_store.faiss_store import FaissStore

store = FaissStore()
# bm25 = Bm25Index()
# bm25.build(store.documents)

# for q in ["医院联网", "Rh阴性", "献浆间隔"]:
#     print("Q", q)
#     for r in bm25.search(q, top_k=3):
#         print(f"  [{r['_index']}] {r['title']}  score={r['bm25_score']:.2f}")

        # 若你已拆出 _search_vector
q = "献浆间隔多久"
v = store._search_vector(q, top_k=5)
b = store.bm25_index.search(q, top_k=5)
h = store.search(q, top_k=3)
print("向量 top3:", [x["content"] for x in v[:3]])
print("="*100)
print("BM25 top3:", [x["content"] for x in b[:3]])
print("="*100)
print("混合 top3:", [x["content"] for x in h])