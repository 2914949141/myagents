# rag/loader/chunk_utils.py
def split_text_into_chunks(
    text: str,
    chunk_size: int = 500,
    overlap: int = 50,
    min_chunk_len: int = 50,
) -> list[str]:
    """纯文本 → 字符串块列表，不含 id/title。 
        chunk_size: 每个文本块的大小（字符数） 
        overlap: 块之间的重叠字符数 
        min_chunk_len: 最小块长度（字符数）
        切分内容，返回字符串块列表"""
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            for sep_pos in range(end, max(start, end - 100), -1):
                if text[sep_pos] in ['\n', '。', '.', '！', '!', '？', '?']:
                    end = sep_pos + 1
                    break
        chunk_text = text[start:end].strip()
        if chunk_text and len(chunk_text) > min_chunk_len:
            chunks.append(chunk_text)
        start += chunk_size - overlap
    return chunks