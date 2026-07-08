from pathlib import Path

from agent_hemo.rag.loader.base_loader import BaseLoader
from agent_hemo.utils.chunk_utils import split_text_into_chunks


class MarkdownLoader(BaseLoader):

    def __init__(self):
        # 每块长度(字数)
        self.chunk_size = 500
        # 重复内容长度(字数)
        self.overlap = 50

    def load(self, file_path: Path) -> str:
        """
            从 Markdown 文件加载文档并分块

            Args:
                file_path: Markdown 文件路径
                chunk_size: 每个文本块的大小（字符数）
                overlap: 块之间的重叠字符数

            Returns:
                文档块列表，每个元素包含 title 和 content
            """
        from pathlib import Path

        path = Path(file_path)
        if not path.exists():
            print(f"⚠️ 文件不存在: {file_path}")
            return []

        # 读取文件内容
        try:
            content = path.read_text(encoding='utf-8')
        except Exception as e:
            print(f"❌ 读取文件失败: {e}")
            return []

        # 提取标题（第一个 # 标题）
        import re
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        title = title_match.group(1) if title_match else path.stem

        # 清理 Markdown 格式
        # 移除代码块
        content = re.sub(r'```[\s\S]*?```', '[代码块]', content)
        # 移除图片标记
        content = re.sub(r'!\[.*?\]\(.*?\)', '', content)
        # 移除链接标记，保留文本
        content = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', content)
        # 移除粗体和斜体标记
        content = re.sub(r'[*_]{1,3}(.*?)[*_]{1,3}', r'\1', content)
        # 移除标题标记
        content = re.sub(r'^#{1,6}\s+', '', content, flags=re.MULTILINE)
        # 移除列表标记
        content = re.sub(r'^[-*+]\s+', '- ', content, flags=re.MULTILINE)
        content = re.sub(r'^\d+\.\s+', '', content, flags=re.MULTILINE)

        # 分块
        text_chunks = split_text_into_chunks(content, self.chunk_size, self.overlap)
        chunks = [
            {
                "id": i,
                "title": f"{title} - 第{i}部分",
                "content": t,
            }
            for i, t in enumerate(text_chunks, start=1)
        ]

        print(f"📄 从 {path.name} 加载了 {len(chunks)} 个文本块")
        return chunks

    def load_documents_from_directory(self, directory: str, pattern: str = "*.md") -> list:
        """
        从目录加载所有 Markdown 文档

        Args:
            directory: 目录路径
            pattern: 文件匹配模式

        Returns:
            所有文档块的列表
        """
        from pathlib import Path

        dir_path = Path(directory)
        if not dir_path.exists():
            print(f"⚠️ 目录不存在: {directory}")
            return []

        all_chunks = []
        md_files = list(dir_path.glob(pattern))

        print(f"\n📂 扫描目录: {directory}")
        print(f"   找到 {len(md_files)} 个 Markdown 文件")

        for md_file in md_files:
            chunks = self.load(str(md_file))
            all_chunks.extend(chunks)

        print(f"✅ 共加载 {len(all_chunks)} 个文本块\n")
        return all_chunks
