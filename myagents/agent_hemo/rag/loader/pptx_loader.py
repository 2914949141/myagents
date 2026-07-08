import re
from pathlib import Path

from markitdown import MarkItDown

from agent_hemo.rag.loader.base_loader import BaseLoader
from agent_hemo.utils.chunk_utils import split_text_into_chunks

_SLIDE_SPLIT = re.compile(r"(?=<!-- Slide number: \d+ -->)")


class PptxLoader(BaseLoader):
    def __init__(self, chunk_size: int = 500, overlap: int = 50):
        self.chunk_size = chunk_size 
        self.overlap = overlap
        self._markitdown = MarkItDown()

    def _convert_to_markdown(self, pptx_path: Path) -> str:
        result = self._markitdown.convert(str(pptx_path))
        return result.text_content or ""

    def _split_slides(self, markdown: str) -> list[tuple[int, str]]:
        slides = []
        for part in _SLIDE_SPLIT.split(markdown):
            part = part.strip()
            if not part:
                continue
            match = re.search(r"<!-- Slide number: (\d+) -->", part)
            page_no = int(match.group(1)) if match else len(slides) + 1
            slides.append((page_no, part))
        return slides

    def _clean_slide_text(self, text: str) -> str:
        text = re.sub(r"<!-- Slide number: \d+ -->", "", text)
        text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
        text = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", text)
        text = re.sub(r"[*_]{1,3}(.*?)[*_]{1,3}", r"\1", text)
        return text.strip()

    def _slide_title(self, text: str, doc_title: str, page_no: int) -> str:
        match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        if match:
            heading = match.group(1).strip()
            if heading:
                return f"{doc_title} - 第{page_no}页 - {heading}"
        return f"{doc_title} - 第{page_no}页"

    def load(self, file_path: Path) -> list:
        path = Path(file_path)
        if not path.exists():
            return []

        markdown = self._convert_to_markdown(path)
        if not markdown.strip():
            print(f"[RAG] 警告: PPTX 未提取到文本: {path.name}")
            return []

        doc_title = path.stem
        chunks = []
        chunk_id = 1

        for page_no, slide_md in self._split_slides(markdown):
            full_text = self._clean_slide_text(slide_md)
            if not full_text:
                continue

            slide_title = self._slide_title(slide_md, doc_title, page_no)

            if len(full_text) <= self.chunk_size:
                chunks.append({
                    "id": chunk_id,
                    "title": slide_title,
                    "content": full_text,
                })
                chunk_id += 1
                continue

            for sub_part, chunk_text in enumerate(
                split_text_into_chunks(full_text, self.chunk_size, self.overlap),
                start=1,
            ):
                chunks.append({
                    "id": chunk_id,
                    "title": f"{slide_title} - 第{sub_part}部分",
                    "content": chunk_text,
                })
                chunk_id += 1

        print(f"📄 从 {path.name} 加载了 {len(chunks)} 个文本块")
        return chunks

    def load_documents_from_directory(self, directory: str, pattern: str = "*.pptx") -> list:
        dir_path = Path(directory)
        if not dir_path.exists():
            print(f"[RAG] 警告: PPTX 目录不存在: {directory}")
            return []

        pptx_files = list(dir_path.glob(pattern))
        print(f"\n[RAG] 扫描 PPTX 目录: {directory}")
        print(f"   找到 {len(pptx_files)} 个 pptx 文件")

        all_chunks = []
        for pptx_file in pptx_files:
            chunks = self.load(pptx_file)
            for c in chunks:
                c["id"] = len(all_chunks) + 1
                all_chunks.append(c)

        print(f"[RAG] PPTX 共加载 {len(all_chunks)} 个文本块\n")
        return all_chunks
