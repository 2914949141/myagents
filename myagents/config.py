"""集中管理项目配置，从 .env 读取环境变量。"""

import os
from pathlib import Path
from datetime import timezone, timedelta

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.resolve()

# 从包目录加载 .env，避免因工作目录不同而读不到配置
load_dotenv(PROJECT_ROOT / ".env")


def _resolve_path(value: str | None, default: Path) -> Path:
    """将 .env 中的相对路径解析为基于 PROJECT_ROOT 的绝对路径。"""
    if not value:
        return default.resolve()
    path = Path(value)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


# ── 路径 ──────────────────────────────────────────────
MEMORY_DIR = _resolve_path(os.getenv("MEMORY_DIR"), PROJECT_ROOT / "memory" / "memory")
SKILLS_DIR = _resolve_path(os.getenv("SKILLS_DIR"), PROJECT_ROOT / "skills")
DOCS_DIR = _resolve_path(os.getenv("DOCS_DIR"), PROJECT_ROOT / "docs" / "md")
LOGS_DIR = PROJECT_ROOT / "logs"

# ── LLM ───────────────────────────────────────────────
LLM_MODEL = os.getenv("LLM_MODEL_ID", "gpt-3.5-turbo")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "60"))

# ── Agent 行为 ────────────────────────────────────────
MAX_TURNS = int(os.getenv("MAX_TURNS", "30"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "2"))
COMPACT_EVERY = int(os.getenv("COMPACT_EVERY", "5"))
COMPACT_RECENT_MESSAGES = int(os.getenv("COMPACT_RECENT_MESSAGES", "4"))

# ── RAG ───────────────────────────────────────────────
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "3"))
HF_ENDPOINT = os.getenv("HF_ENDPOINT", "https://hf-mirror.com")

# ── 工具 ──────────────────────────────────────────────
COMMAND_TIMEOUT = int(os.getenv("COMMAND_TIMEOUT", "30"))

# ── 时区 ──────────────────────────────────────────────
UTC8 = timezone(timedelta(hours=8))
