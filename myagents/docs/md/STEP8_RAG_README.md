# Step 8: RAG (检索增强生成) 教程

## 📚 概述

`step8_rag.py` 演示了如何为 AI Agent 添加 RAG (Retrieval-Augmented Generation) 能力，使用 FAISS 实现高效的向量检索。

---

## 🎯 什么是 RAG？

RAG (Retrieval-Augmented Generation) 是一种结合**信息检索**和**文本生成**的技术：

1. **检索阶段**: 从知识库中检索与用户问题相关的文档
2. **生成阶段**: LLM 基于检索结果生成准确的回答

**优势**:
- ✅ 减少幻觉（Hallucination）
- ✅ 提供可追溯的答案来源
- ✅ 支持领域特定知识
- ✅ 无需微调 LLM

---

## 🏗️ 架构设计

```
用户问题
   ↓
[向量化] → Sentence Transformer
   ↓
[检索] → FAISS 向量索引
   ↓
相关文档 (Top-K)
   ↓
[注入上下文] → System Prompt
   ↓
[生成] → LLM
   ↓
最终回答
```

---

## 🔧 核心组件

### 1. VectorStore (向量存储)

基于 FAISS 实现的向量检索系统：

```python
class VectorStore:
    - add_document()      # 添加单个文档
    - add_documents()     # 批量添加文档
    - search()            # 语义检索
    - get_document_count() # 获取文档数量
```

**关键技术**:
- **Embedding 模型**: `paraphrase-multilingual-MiniLM-L12-v2`
  - 支持多语言（中文、英文等）
  - 向量维度: 384
  - 轻量级，速度快
  
- **FAISS 索引**: `IndexFlatL2`
  - 使用 L2 距离（欧氏距离）
  - 精确搜索，适合小规模数据
  - 可扩展为 IVF、HNSW 等高级索引

### 2. RAG 工具

将检索功能封装为 LLM 可调用的工具：

```python
{
    "name": "rag_search",
    "description": "从知识库中检索与问题相关的信息",
    "parameters": {
        "query": "要检索的问题或关键词",
        "top_k": "返回最相关的文档数量"
    }
}
```

### 3. 知识库

示例包含 10 个技术主题：
- Python 基础、列表推导式、装饰器
- AI Agent、机器学习、深度学习
- FAISS、RAG、向量嵌入
- RESTful API

---

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install faiss-cpu sentence-transformers numpy
```

### 2. 运行示例

```bash
cd build-agent-example/mycode
python step8_rag.py
```

### 3. 测试用例

程序会自动执行以下测试：

**测试 1**: Python 相关问题
```
问: "Python 的列表推导式是什么？怎么用？"
→ 调用 rag_search 检索相关知识
→ 基于检索结果回答
```

**测试 2**: AI Agent 相关问题
```
问: "什么是 AI Agent？它有什么特点？"
→ 检索 AI Agent 定义和特征
→ 生成准确回答
```

**测试 3**: 混合工具使用
```
问: "先查一下机器学习的基础知识，然后计算 2 的 10 次方"
→ 先调用 rag_search 检索机器学习知识
→ 再调用 calculate 计算数学表达式
```

**测试 4**: 知识库外的问题
```
问: "量子计算机的原理是什么？"
→ 检索失败，如实告知用户知识库中没有相关信息
```

---

## 💡 代码解析

### 第一步：准备知识库数据

```python
KNOWLEDGE_BASE = [
    {
        "id": 1,
        "title": "Python 基础",
        "content": "Python 是一种广泛使用的高级编程语言..."
    },
    # ... 更多文档
]
```

### 第二步：初始化向量存储

```python
vector_store = VectorStore()
# 自动加载 Sentence Transformer 模型
# 初始化 FAISS 索引
```

### 第三步：构建知识库

```python
vector_store.add_documents(KNOWLEDGE_BASE)
# 对每个文档：
# 1. 组合标题和内容
# 2. 生成向量嵌入
# 3. 添加到 FAISS 索引
# 4. 保存元数据
```

### 第四步：创建 RAG 工具

```python
rag_tool_def, rag_search_func = create_rag_tool(vector_store)
# 返回工具定义 (JSON Schema) 和工具函数
```

### 第五步：Agent 循环

```python
messages = [
    {"role": "system", "content": "你是一个智能助手..."},
    {"role": "user", "content": user_message}
]

# LLM 决定是否调用 rag_search 工具
response = llm.invoke(messages, tools=TOOLS)

# 执行工具调用
if response.tool_calls:
    for tool_call in response.tool_calls:
        result = execute_tool(tool_call, rag_search_func)
        messages.append(result)
```

---

## 🔍 向量检索原理

### 1. 文本向量化

```
文本: "Python 是一种编程语言"
  ↓ [Sentence Transformer]
向量: [0.12, -0.45, 0.78, ..., 0.33]  (384维)
```

**关键特性**:
- 语义相似的文本，向量距离近
- 支持多语言
- 固定长度输出

### 2. 相似度计算

使用 **L2 距离**（欧氏距离）:

```python
distance = ||query_vector - doc_vector||²
```

距离越小 → 越相关

转换为相关性分数:

```python
relevance_score = 1 / (1 + distance)
```

### 3. FAISS 搜索

```python
distances, indices = index.search(query_vector, k=3)
# 返回最近的 3 个文档及其距离
```

---

## 📊 性能优化建议

### 1. 选择合适的 Embedding 模型

| 模型 | 维度 | 速度 | 质量 | 适用场景 |
|------|------|------|------|----------|
| paraphrase-multilingual-MiniLM-L12-v2 | 384 | ⚡⚡⚡ | ⭐⭐⭐ | 通用场景 |
| all-MiniLM-L6-v2 | 384 | ⚡⚡⚡⚡ | ⭐⭐ | 快速原型 |
| all-mpnet-base-v2 | 768 | ⚡⚡ | ⭐⭐⭐⭐ | 高质量需求 |
| text-embedding-ada-002 (OpenAI) | 1536 | ⚡ | ⭐⭐⭐⭐⭐ | 生产环境 |

### 2. 选择合适的 FAISS 索引

| 索引类型 | 速度 | 内存 | 准确性 | 适用规模 |
|----------|------|------|--------|----------|
| IndexFlatL2 | 慢 | 高 | 100% | < 10万 |
| IndexIVFFlat | 快 | 中 | 95% | 10万-1000万 |
| IndexHNSW | 很快 | 中 | 98% | < 100万 |
| IndexPQ | 很快 | 低 | 90% | > 1000万 |

### 3. 文本分块策略

对于长文档，应该分块：

```python
def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """
    将长文本分割为带有重叠的小块，以保持上下文连贯性。
    
    💡 为什么需要 overlap (重叠)？
    ---------------------------
    想象你在读一本长书，每次只读一页（chunk）。
    如果这一页的结尾刚好切断了一个句子或一个关键概念，
    下一页开头又是新的内容，那么：
    1. **语义断裂**：当前块可能丢失了关键信息的后半部分。
    2. **检索失败**：如果用户的问题恰好涉及那个被切断的概念，
       向量模型可能因为信息不完整而无法准确匹配。
    
    ✅ Overlap 的作用：
    让相邻的两个块共享一部分内容（如最后50个字符）。
    这样即使关键信息在边界处，它也会完整地出现在至少一个块中，
    或者在两个块中都有上下文支撑，从而提高检索准确率。
    
    Args:
        text: 需要分块的原始文本
        chunk_size: 每个文本块的最大字符数 (窗口大小)
        overlap: 相邻文本块之间的重叠字符数 (步长 = chunk_size - overlap)
        
    Returns:
        分割后的文本块列表
        
    Example:
        Text: "ABCDEFGHIJK" (11 chars)
        Chunk Size: 5, Overlap: 2
        
        Chunk 1: ABCDE (start=0, end=5)
        Chunk 2: CDEFG (start=3, end=8)  <- "CDE" 是重叠部分
        Chunk 3: EFGHI (start=6, end=11) <- "EF" 是重叠部分
        Chunk 4: IJK   (start=9, end=11)
    """
    if not text:
        return []
        
    # 基本参数校验
    if overlap >= chunk_size:
        raise ValueError("overlap 必须小于 chunk_size")
    if chunk_size <= 0:
        raise ValueError("chunk_size 必须大于 0")
        
    chunks = []
    start = 0
    text_len = len(text)
    
    while start < text_len:
        end = min(start + chunk_size, text_len)
        chunk = text[start:end]
        chunks.append(chunk)
        
        # 如果已经到达文本末尾，则退出循环
        if end == text_len:
            break
            
        # 移动起始位置：
        # 正常情况向前移动 chunk_size 个字符
        # 但为了保留 overlap，我们只移动 (chunk_size - overlap) 个字符
        # 这样下一个块就会包含当前块末尾的 overlap 个字符
        start += chunk_size - overlap
        
    return chunks
```

---

## 🎓 学习要点

### 1. RAG vs Fine-tuning

| 特性 | RAG | Fine-tuning |
|------|-----|-------------|
| 更新知识 | ✅ 只需更新知识库 | ❌ 需重新训练 |
| 成本 | 💰 低 | 💰💰💰 高 |
| 可解释性 | ✅ 可追溯来源 | ❌ 黑盒 |
| 实时性 | ✅ 即时生效 | ❌ 训练耗时 |
| 适用场景 | 事实性知识 | 风格迁移、任务特化 |

### 2. 何时使用 RAG？

✅ **适合**:
- 问答系统
- 客服机器人
- 文档检索
- 知识密集型任务

❌ **不适合**:
- 创意写作
- 代码生成
- 逻辑推理

### 3. 常见问题

**Q1: 如何提高检索准确率？**
- 使用更好的 Embedding 模型
- 调整 top_k 参数
- 添加元数据过滤
- 使用混合检索（向量 + 关键词）

**Q2: 如何处理大规模知识库？**
- 使用分布式 FAISS
- 切换到 Milvus/Qdrant 等专业向量数据库
- 使用分层检索策略

**Q3: 如何评估 RAG 效果？**
- 检索准确率 (Precision@K)
- 召回率 (Recall@K)
- 答案质量 (人工评估或 LLM-as-Judge)

---

## 🔗 扩展阅读

- [FAISS 官方文档](https://faiss.ai/)
- [Sentence Transformers](https://www.sbert.net/)
- [RAG 论文](https://arxiv.org/abs/2005.11401)
- [LangChain RAG](https://python.langchain.com/docs/use_cases/question_answering/)

---

## 📝 下一步

1. **添加真实数据**: 从 Wikipedia、技术文档等加载真实知识
2. **文本分块**: 实现智能分块策略
3. **混合检索**: 结合 BM25 关键词检索
4. **重排序**: 使用 Cross-Encoder 优化检索结果
5. **持久化**: 保存和加载 FAISS 索引
6. **可视化**: 展示检索过程和结果

---

## ✨ 总结

通过这个教程，你学习了：

1. ✅ RAG 的基本概念和工作流程
2. ✅ 使用 Sentence Transformer 生成文本向量
3. ✅ 使用 FAISS 构建向量索引
4. ✅ 实现语义检索功能
5. ✅ 将检索结果注入到 LLM 上下文
6. ✅ 构建完整的 RAG Agent

祝你学习愉快！🎉
