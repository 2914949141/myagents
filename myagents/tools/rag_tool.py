
from myagents.tools.base_tool import BaseTool
from myagents.config import RAG_TOP_K


_faiss_store = None

class RagTool(BaseTool):
    """指定rag工具 - 从知识库中检索相关信息"""

    name = "rag_search"
    description = "从知识库中检索与问题相关的信息。在回答问题前，先调用此工具获取相关知识。"

    @classmethod
    def get_parameters(cls) -> dict:
        """返回参数定义"""
        return {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "要检索的问题或关键词"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "返回最相关的文档数量，默认 3",
                        "default": 3
                    }
                },
                "required": ["query"]
            }

    def get_faiss_store(self):
        global _faiss_store
        if _faiss_store is None:
            from myagents.rag.vector_store.faiss_store import FaissStore
            _faiss_store = FaissStore()
        return _faiss_store

    def execute(self, tool_call) -> str:
        import json
        args = json.loads(tool_call.function.arguments)
        query = args.get('query')
        top_k = args.get('top_k', RAG_TOP_K)
        """
                从知识库中检索相关信息

                Args:
                    query: 查询问题
                    top_k: 返回最相关的 K 个文档（默认 3）

                Returns:
                    格式化的检索结果
                """
        print(f"\n🔍 检索知识库: '{query}'")

        # 执行向量搜索
        results = self.get_faiss_store().search(query, top_k=top_k)

        if not results:
            return "抱歉，知识库中没有找到相关信息。"

        # 格式化输出
        output_lines = [f"📚 找到 {len(results)} 条相关知识:\n"]

        for i, result in enumerate(results, 1):
            output_lines.append(f"[{i}] {result['title']}")
            output_lines.append(f"    相关性: {result['relevance_score']:.2%}")
            output_lines.append(f"    内容: {result['content']}")
            output_lines.append("")

        return "\n".join(output_lines)
