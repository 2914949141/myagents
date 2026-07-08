# rag/vector_store/index_persistence.py
"""
RAG 索引持久化 + manifest 失效检测

职责：
1、扫描源文件目录, 生成manifest
2、比较 manifest,  判断缓存是否有效
3、save / load FAISS、documents、BM25 分词语料
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# 缓存目录下的文件名 （常量集中管理）
MANIFEST_FILE = "manifest.json"
FAISS_INDEX_FILE = "faiss_index"
DOCUMENTS_FILE = "documents.json"
BM25_CORPUS_FILE = "bm25_corpus.json"

def _rel(path: Path, root: Path) -> str:
    """转成相对项目根的路径, manifest 里更好读"""
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path.resolve())

def scan_source_files(*directories: Path, patterns: tuple[str, ...] = ("*.md", "*.pptx")) -> list[dict[str, Any]]:
    """
    扫描知识库源文件,  收集path / mtime / size
    只扫「原始文件」, 不扫缓存目录。
    """
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()

    for directory in directories:
        if not directory.exists():
            continue
        for pattern in patterns:
            for file_path in sorted(directory.glob(pattern)):
                key = str(file_path.resolve())
                if key in seen:
                    continue
                seen.add(key)
                stat = file_path.stat()
                entries.append({
                    "path": key,
                    "mtime": stat.st_mtime,
                    "size": stat.st_size
                })
    return entries


def build_manifest(
    *,
    project_root: Path,
    source_dirs: list[Path],
    embedding_model: str,
    chunk_size: int,
    chunk_overlap: int,
) -> dict[str, Any]:
    """
    组装 manifest.json  {version, sources文件列表, embedding_model, chunk_size, chunk_overlap}
    """
    # 返回所有文件的path、mtime、size
    raw_entries = scan_source_files(*source_dirs)
    sources = []
    for e in raw_entries:
        sources.append({
            "path": _rel(Path(e["path"]), project_root),
            "mtime": e["mtime"],
            "size": e["size"]
        })
    sources.sort(key=lambda x: x["path"])
    return {
        "version": "1.0.0",
        "sources": sources,
        "embedding_model": embedding_model,
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap
    }

def manifest_equal(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """比较两个 manifest 是否相等"""
    return a == b

def cache_files_complete(index_dir: Path) -> bool:
    """检查缓存目录下的文件是否存在"""
    required = [MANIFEST_FILE, FAISS_INDEX_FILE, DOCUMENTS_FILE, BM25_CORPUS_FILE]
    return all((index_dir / name).exists() for name in required)

def load_manifest(index_dir: Path) -> dict[str, Any] | None:
    """加载 manifest.json"""
    path = index_dir / MANIFEST_FILE
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))

def save_manifest(index_dir: Path, manifest: dict[str, Any]) -> None:
    """保存 manifest.json"""
    index_dir.mkdir(parents=True, exist_ok=True)
    (index_dir / MANIFEST_FILE).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

def save_documents(index_dir: Path, documents: list[dict[str, Any]]) -> None:
    # documents 里都是普通 dict, json 可序列化
    (index_dir / DOCUMENTS_FILE).write_text(json.dumps(documents, ensure_ascii=False, indent=2), encoding="utf-8")

def load_documents(index_dir: Path) -> list[dict[str, Any]]:
    return json.loads((index_dir / DOCUMENTS_FILE).read_text(encoding="utf-8"))

def save_bm25_corpus(index_dir: Path, tokenized_corpus: list[list[str]]) -> None:
    (index_dir / BM25_CORPUS_FILE).write_text(json.dumps(tokenized_corpus, ensure_ascii=False), encoding="utf-8")

def load_bm25_corpus(index_dir: Path) -> list[list[str]]:
    return json.loads((index_dir / BM25_CORPUS_FILE).read_text(encoding="utf-8"))

def save_faiss_index(index_dir: Path, index) -> None:
    import faiss
    faiss.write_index(index, str(index_dir / FAISS_INDEX_FILE))

def load_faiss_index(index_dir: Path):
    import faiss
    return faiss.read_index(str(index_dir / FAISS_INDEX_FILE))

def is_cache_valid(
    index_dir: Path,
    current_manifest: dict[str, Any]
) -> bool:
    """
    缓存有效的三个条件：
    1、缓存文件齐全
    2、磁盘上有manifest
    3、磁盘manifest与当前的manifest相等
    """
    if not cache_files_complete(index_dir):
        return False
    saved = load_manifest(index_dir)
    if saved is None:
        return False
    return manifest_equal(saved, current_manifest)