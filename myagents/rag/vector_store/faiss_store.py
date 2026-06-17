from pathlib import Path

import numpy as np
import os

from myagents.config import DOCS_DIR, RAG_TOP_K, HF_ENDPOINT
from myagents.rag.loader.markdown_loader import MarkdownLoader

TOP_K = RAG_TOP_K

os.environ['HF_ENDPOINT'] = HF_ENDPOINT
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'
md_dir = DOCS_DIR

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


class FaissStore:
    """基于 FAISS 的向量存储和检索系统"""

    def __init__(self, embedding_model_name: str = "all-MiniLM-L6-v2"):
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

        print(f"📦 加载 Embedding 模型: {embedding_model_name}")
        self.model = SentenceTransformer(embedding_model_name)
        self.dimension = self.model.get_sentence_embedding_dimension()

        # 初始化 FAISS 索引（使用 L2 距离）
        self.index = faiss.IndexFlatL2(self.dimension)

        # 存储文档元数据
        self.documents = []
        self.embeddings = []

        print(f"✅ 向量维度: {self.dimension}")
        print(f"✅ FAISS 索引已初始化")

        # self.add_documents(KNOWLEDGE_BASE)
        # 切分md目录下md文件
        index_chunk = MarkdownLoader().load_documents_from_directory(md_dir, "*.md")
        if index_chunk:
            self.add_documents(index_chunk)
            print(f"✅ md目录下文件 已添加到知识库")
        else:
            print("⚠️ 未加载到md文件")

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

    def search(self, query: str, top_k: int = TOP_K) -> list:
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
                    "id": doc["id"],
                    "title": doc["title"],
                    "content": doc["content"],
                    "distance": float(distances[0][i]), # 距离越小越相关
                    "relevance_score": 1 / (1 + distances[0][i]) # 转换为相关性分数
                })
        return results

    def get_document_count(self) -> int:
        """获取文档数量"""
        return len(self.documents)