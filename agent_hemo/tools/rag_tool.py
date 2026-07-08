
from agent_hemo.tools.base_tool import BaseTool
from agent_hemo.settings import RAG_TOP_K


_faiss_store = None

# 每块内容最大字符数，避免 RAG 结果撑爆 LLM 上下文
RAG_CONTENT_MAX_LEN = 400


class RagTool(BaseTool):
    """指定rag工具 - 从知识库中检索相关信息"""

    name = "rag_search"
    description = ("从血站业务知识库检索规程/标准/流程。"
                "仅用于业务知识问答，不用于生成日报、周报、临期血浆告警。"
                "用户要报表或预警时不要调用本工具。")

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
            from agent_hemo.rag.vector_store.faiss_store import FaissStore
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
            print(f"[RAG] 警告: 没有找到相关信息")
            return "抱歉，知识库中没有找到相关信息。"

        # 格式化输出
        output_lines = [f"📚 找到 {len(results)} 条相关知识:\n"]

        for i, result in enumerate(results, 1):
            title = result['title']
            content = result['content']
            if len(content) > RAG_CONTENT_MAX_LEN:
                content = content[:RAG_CONTENT_MAX_LEN] + "…"

            output_lines.append(f"[{i}] 来源: {title}")
            output_lines.append(f"    相关性: {result.get('relevance_score')}")
            output_lines.append(f"    内容: {content}")
            output_lines.append("")

            print(f"[{i}] 来源: {title}")
            print(f"    相关性: {result.get('relevance_score')}")
            print("")

        return "\n".join(output_lines)
