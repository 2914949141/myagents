"""集中管理项目配置，从 .env 读取环境变量。"""

import os
from pathlib import Path
from datetime import timezone, timedelta

from dotenv import load_dotenv

# 项目根目录（Agent-Hemo/），与包目录 agent_hemo/ 区分
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_ROOT = Path(__file__).resolve().parent

load_dotenv(PROJECT_ROOT / ".env")


def _resolve_path(value: str | None, default: Path) -> Path:
    """将 .env 中的相对路径解析为基于 PROJECT_ROOT 的绝对路径。"""
    if not value:
        return default.resolve()
    return resolve_project_path(value)


def resolve_project_path(path: str | Path) -> Path:
    """将相对路径解析为基于 PROJECT_ROOT 的绝对路径。"""
    p = Path(path)
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    return p.resolve()


# ── 路径 ──────────────────────────────────────────────
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"
STATIC_DIR = PACKAGE_ROOT / "static"

MEMORY_DIR = _resolve_path(os.getenv("MEMORY_DIR"), DATA_DIR / "memory")
SKILLS_DIR = _resolve_path(os.getenv("SKILLS_DIR"), DATA_DIR / "skills")
KNOWLEDGE_DIR = _resolve_path(
    os.getenv("KNOWLEDGE_DIR") or os.getenv("DOCS_DIR"),
    PROJECT_ROOT / "knowledge",
)
DOCS_DIR = KNOWLEDGE_DIR  # 兼容旧变量名
PPTX_DIR = _resolve_path(os.getenv("PPTX_DIR"), DATA_DIR / "sources" / "pptx")
REPORTS_DIR = _resolve_path(os.getenv("REPORTS_DIR"), DATA_DIR / "reports")

WORKFLOW_CHECKPOINT_DB = _resolve_path(
    os.getenv("WORKFLOW_CHECKPOINT_DB"),
    DATA_DIR / "workflow_checkpoints.sqlite",
)

# ── API ───────────────────────────────────────────────
API_KEY = os.getenv("API_KEY", "321")
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))

# 告警流水线
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "") or os.getenv("DINGTALK_SECRET", "")
ALERT_CSV_PATH = os.getenv("ALERT_CSV_PATH", "data/bag_info.csv")
ALERT_WARNING_DAYS = int(os.getenv("ALERT_WARNING_DAYS", "30"))

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
COMMAND_AUTO_APPROVE = os.getenv("COMMAND_AUTO_APPROVE", "false").lower() == "true"

# ── RAG ───────────────────────────────────────────────
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "3"))
RAG_INDEX_DIR = _resolve_path(os.getenv("RAG_INDEX_DIR"), DATA_DIR / "rag_index")
RAG_CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "500"))
RAG_CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "50"))

HF_ENDPOINT = os.getenv("HF_ENDPOINT", "https://hf-mirror.com")
RAG_EMBEDDING_MODEL = os.getenv(
    "RAG_EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2"
)

# ── JWT ───────────────────────────────────────────────
JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

# 单用户登录
AUTH_USERNAME = os.getenv("AUTH_USERNAME", "admin")
AUTH_PASSWORD = os.getenv("AUTH_PASSWORD", "")

# ── 限流 ──────────────────────────────────────────────
RATE_LIMIT_DEFAULT = os.getenv("RATE_LIMIT_DEFAULT", "30/minute")
RATE_LIMIT_CHAT = os.getenv("RATE_LIMIT_PER_USER", "10/minute")

# ── 工具 ──────────────────────────────────────────────
COMMAND_TIMEOUT = int(os.getenv("COMMAND_TIMEOUT", "30"))

# ── 时区 ──────────────────────────────────────────────
UTC8 = timezone(timedelta(hours=8))
