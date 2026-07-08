from pathlib import Path

import numpy as np
import os

from agent_hemo.settings import DOCS_DIR, PPTX_DIR, RAG_TOP_K, HF_ENDPOINT, RAG_EMBEDDING_MODEL, RAG_INDEX_DIR
from agent_hemo.rag.loader.markdown_loader import MarkdownLoader
from agent_hemo.rag.loader.pptx_loader import PptxLoader
from agent_hemo.rag.vector_store.bm_index import Bm25Index
from agent_hemo.rag.vector_store.hybrid_search import hybrid_search
from agent_hemo.rag.vector_store.reranker import Reranker
from agent_hemo.rag.vector_store.index_persistence import is_cache_valid

TOP_K = RAG_TOP_K

os.environ['HF_ENDPOINT'] = HF_ENDPOINT
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'
md_dir = DOCS_DIR
pptx_dir = PPTX_DIR

# 模拟知识库文档（实际项目中可以从数据库、文件系统加载）
KNOWLEDGE_BASE = [
    {
        "id": 1,
        "title": "Python 基础",
        "content": "Python 是一种广泛使用的高级编程语言，由 Guido van Rossum 于 1991 年首次发布。Python 设计哲学强调代码的可读性和简洁的语法，允许程序员用更少的代码行表达概念。"
    },
    {
        "id": 2,
        "title": "Python 列表推导式",
        "content": "列表推导式是 Python 中一种简洁的创建列表的方法。基本语法是：[expression for item in iterable if condition]。例如：[x**2 for x in range(10) if x % 2 == 0] 会生成 [0, 4, 16, 36, 64]。"
    },
    {
        "id": 3,
        "title": "AI Agent 定义",
        "content": "AI Agent（人工智能代理）是能够感知环境、做出决策并采取行动的智能系统。Agent 通常具备自主性、反应性、主动性和社交能力等特征。"
    },
    {
        "id": 4,
        "title": "机器学习基础",
        "content": "机器学习是人工智能的一个分支，使计算机能够从数据中学习，而无需显式编程。主要类型包括：监督学习、无监督学习、强化学习和半监督学习。"
    },
    {
        "id": 5,
        "title": "深度学习",
        "content": "深度学习是机器学习的子领域，使用多层神经网络来学习数据的层次化表示。典型应用包括图像识别、自然语言处理和语音识别。常见的框架有 TensorFlow、PyTorch 等。"
    },
    {
        "id": 6,
        "title": "FAISS 向量搜索",
        "content": "FAISS (Facebook AI Similarity Search) 是 Facebook 开发的用于高效相似性搜索和密集向量聚类的库。它支持数十亿向量的搜索，提供多种索引类型，如 IVF、HNSW、PQ 等。"
    },
    {
        "id": 7,
        "title": "RAG 技术",
        "content": "RAG (Retrieval-Augmented Generation) 是一种结合信息检索和文本生成的技术。它先从知识库中检索相关文档，然后将检索结果作为上下文提供给 LLM，从而生成更准确、更有依据的回答。"
    },
    {
        "id": 8,
        "title": "向量嵌入 (Embedding)",
        "content": "向量嵌入是将文本、图像等数据转换为固定长度的数值向量的过程。语义相似的内容在向量空间中距离较近。常用的 embedding 模型有 BERT、Sentence-BERT、OpenAI Embeddings 等。"
    },
    {
        "id": 9,
        "title": "Python 装饰器",
        "content": "装饰器是 Python 中的一种高级特性，允许在不修改原函数代码的情况下扩展函数功能。使用 @decorator 语法。例如：@staticmethod、@classmethod、@property 都是内置装饰器。"
    },
    {
        "id": 10,
        "title": "RESTful API",
        "content": "RESTful API 是一种基于 HTTP 协议的 Web API 设计风格，遵循 REST (Representational State Transfer) 架构风格。核心原则包括：无状态、统一接口、资源导向、使用标准 HTTP 方法 (GET, POST, PUT, DELETE)。"
    }
]


def _get_embedding_dimension(model) -> int:
    """兼容 sentence-transformers 新旧 API。"""
    if hasattr(model, "get_embedding_dimension"):
        return model.get_embedding_dimension()
    return model.get_sentence_embedding_dimension()


class FaissStore:
    """基于 FAISS 的向量存储和检索系统"""

    def __init__(self, embedding_model_name: str = RAG_EMBEDDING_MODEL):
        """
        初始化向量存储

        Args:
            embedding_model_name: Sentence Transformer 模型名称
                - all-MiniLM-L6-v2: 快速、轻量（推荐）
                - paraphrase-multilingual-MiniLM-L12-v2: 支持多语言
        """
        try:
            from sentence_transformers import SentenceTransformer
            import faiss
        except ImportError:
            print("❌ 缺少必要的依赖包")
            print("请运行: pip install faiss-cpu sentence-transformers numpy")
            raise

        print(f"[RAG] 加载 Embedding 模型: {embedding_model_name}")
        try:
            self.model = SentenceTransformer(embedding_model_name, device="cpu")
        except OSError as e:
            raise OSError(
                f"Embedding 模型加载失败（常见原因：内存/页面文件不足）。"
                f"可在 .env 设置 RAG_EMBEDDING_MODEL=all-MiniLM-L6-v2 使用更轻量模型。"
                f"原始错误: {e}"
            ) from e
        self.dimension = _get_embedding_dimension(self.model)

        # 初始化 FAISS 索引（使用 L2 距离）
        self.index = faiss.IndexFlatL2(self.dimension)

        # 存储文档元数据
        self.documents = []
        self.embeddings = []
        self.reranker = None

        manifest = self._current_manifest()
        if is_cache_valid(RAG_INDEX_DIR, manifest):
            print("[RAG] 缓存有效，直接加载...")
            self._load_from_cache(RAG_INDEX_DIR)
        else: # 缓存无效或不存在，开始重建
            print("[RAG] 缓存无效或不存在，开始重建...")
            self._rebuild_from_scores()
            if self.documents:
                self._save_to_cache(RAG_INDEX_DIR, manifest)
            else:
                print("[RAG] 重建失败，没有文档")
        print("[RAG] 混合检索索引就绪")

    def _get_reranker(self):
        if self.reranker is None:
            self.reranker = Reranker()
        return self.reranker

    def add_document(self, doc_id: int, title: str, content: str):
        """
        添加文档到向量库

        Args:
            doc_id: 文档 ID
            title: 文档标题
            content: 文档内容
        """
        # 组合标题和内容作为文本
        text = f"{title}: {content}"
        # 生成向量嵌入
        embedding = self.model.encode([text])[0]

        # 添加FAISS索引
        self.index.add(np.array([embedding]).astype('float32'))
        # 保存文档源数据
        self.documents.append({
            "id": doc_id,
            "title": title,
            "content": content,
            "text": text
        })
        self.embeddings.append(embedding)

        print(f"  📄 添加文档 [{doc_id}]: {title}")

    def add_documents(self, documents: list):
        """批量添加文档"""
        print(f"\n📚 开始构建知识库，共 {len(documents)} 个文档...")
        for doc in documents:
            self.add_document(doc["id"], doc["title"], doc["content"])
        print(f"✅ 知识库构建完成，共 {len(self.documents)} 个文档\n")

    def _search_vector(self, query: str, top_k: int = TOP_K) -> list:
        """
        搜索与查询最相关的文档

        Args:
            query: 查询文本
            top_k: 返回最相关的 K 个文档

        Returns:
            相关文档列表，按相关性排序
        """
        if len(self.documents) == 0:
            return []
        # 生成查询向量
        query_embedding = self.model.encode([query])[0]
        # 在FAISS中搜索
        distances, indices = self.index.search(
            np.array([query_embedding]).astype('float32'),
            min(top_k, len(self.documents))
        )

        # 组装结果
        results = []
        for i, idx in enumerate(indices[0]):
            if idx != -1:  # -1 表示无效索引
                doc = self.documents[idx]
                results.append({
                    "_index": int(idx),
                    "id": doc["id"],
                    "title": doc["title"],
                    "content": doc["content"],
                    "distance": float(distances[0][i]), # 距离越小越相关
                    "relevance_score": 1 / (1 + distances[0][i]) # 转换为相关性分数
                })
        return results

    def search(self, query: str, top_k: int = TOP_K, recall_k: int = 20) -> list:
        """
        混合检索入口
        recall_k 每路先召回多少条（建议 20）
        top_k 为最终返回条数（给 Agent，通常 3）
        """ 
        if not self.documents:
            return []
        vector_hits = self._search_vector(query, recall_k)
        bm25_hits = self.bm25_index.search(query, recall_k)
        merged = hybrid_search(vector_hits, bm25_hits, self.documents, top_k=recall_k)
        return self._get_reranker().rerank(query, merged, top_k=top_k)


    def get_document_count(self) -> int:
        """获取文档数量"""
        return len(self.documents)

    def _current_manifest(self) -> dict:
        from agent_hemo.settings import RAG_CHUNK_SIZE, RAG_CHUNK_OVERLAP, PROJECT_ROOT
        from agent_hemo.rag.vector_store.index_persistence import build_manifest

        return build_manifest(
            project_root=PROJECT_ROOT,
            source_dirs=[md_dir, pptx_dir],
            embedding_model=RAG_EMBEDDING_MODEL,
            chunk_size=RAG_CHUNK_SIZE,
            chunk_overlap=RAG_CHUNK_OVERLAP
        )
    
    def _rebuild_from_scores(self) -> None:
        """从源文件重新加载并建索引"""
        all_chunks = []
        all_chunks += MarkdownLoader().load_documents_from_directory(md_dir, "*.md")
        all_chunks += PptxLoader().load_documents_from_directory(pptx_dir, "*.pptx")
        if not all_chunks:
            print("[RAG] 警告: 未加载到任何 md/pptx 文档")
            self.bm25_index = Bm25Index()
            return

        self.add_documents(all_chunks)
        self.bm25_index = Bm25Index()
        self.bm25_index.build(self.documents)

    def _load_from_cache(self, index_dir: Path) -> None:
        """从磁盘回复FAISS + documents + BM25 分词语料"""
        from agent_hemo.rag.vector_store.index_persistence import load_faiss_index, load_documents, load_bm25_corpus

        self.index = load_faiss_index(index_dir)
        self.documents = load_documents(index_dir)
        self.bm25_index = Bm25Index()
        self.bm25_index.load_from_corpus(self.documents, load_bm25_corpus(index_dir))

        print(f"[RAG] 从缓存加载索引完成，共 {len(self.documents)} 块")

    def _save_to_cache(self, index_dir: Path, manifest: dict) -> None:
        """重建manifest、FAISS、documents、BM25后写入磁盘"""
        from agent_hemo.rag.vector_store.index_persistence import save_faiss_index, save_documents, save_bm25_corpus, save_manifest

        index_dir.mkdir(parents=True, exist_ok=True)
        save_faiss_index(index_dir, self.index)
        save_documents(index_dir, self.documents)
        save_bm25_corpus(index_dir, self.bm25_index._tokenized_corpus)
        save_manifest(index_dir, manifest)
        print(f"[RAG] 写入缓存完成，共 {len(self.documents)} 块")