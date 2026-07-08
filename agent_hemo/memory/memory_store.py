import json
from pathlib import Path
from datetime import datetime

from agent_hemo.settings import MEMORY_DIR, UTC8, COMPACT_RECENT_MESSAGES


# =============Memory系统实现============================================
# Memory三层架构：
# 1. 原始层 (Raw Layer): history.jsonl - 记录所有对话历史
# 2. 中期层 (Episodic Layer): 按日期存储的情景记忆 {date}.md
# 3. 长期层 (Long-term Layer): MEMORY.md - 核心目标、关键事实
class MemoryStore:


    """三层记忆系统"""
    def __init__(self, memory_dir: Path = MEMORY_DIR):
        self.memory_dir = memory_dir
        self.memory_file = memory_dir / 'MEMORY.md'
        self.history_file = memory_dir / 'history.jsonl'
        self._ensure()


    def _ensure(self):
        """保证文件夹目录和文件的创建"""
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        if not self.memory_file.exists():
            self.memory_file.write_text(
                "# 长期记忆\n\n"
                "此文件常驻于上下文中，记录核心目标，当前任务与关键事实"
            )
        if not self.history_file.exists():
            self.history_file.write_text("")

    # ── 原始层：记录所有对话 ──────────────────────────────
    def append_history(self, role: str, content: str) -> None:
        """追加一个对话到历史文件"""
        row = {
            "role": role,
            "time": datetime.now(UTC8).isoformat(timespec="seconds"),
            "content": content if isinstance(content, str) else str(content)
        }
        with self.history_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


    # ── 中期层：按日期的情景记忆 ──────────────────────────
    def today_episode_path(self) -> Path:
        """返回当天的情景记忆路径"""
        date = datetime.now(UTC8).strftime("%Y-%m-%d")
        return self.memory_dir / f"{date}.md"

    def read_today_episode(self) -> str:
        """读取当天的情景记忆"""
        p = self.today_episode_path()
        if p.exists():
            try:
                return p.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                try:
                    return p.read_text(encoding="gbk")
                except UnicodeDecodeError:
                    return f"{p.stem} 情景记忆\n"
        else:
            return f"{p.stem} 情景记忆\n"

    def append_episode(self, content: str) -> str:
        """追加写入当天的情景记忆"""
        p = self.today_episode_path()
        if p.exists():
            try:
                existing = p.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                try:
                    existing = p.read_text(encoding="gbk")
                except UnicodeDecodeError:
                    existing = f"{p.stem} 情景记忆\n"
        else:
            existing = f"{p.stem} 情景记忆\n"
        new_text = existing.rstrip() + "\n" + content.strip()
        p.write_text(new_text, encoding="utf-8")

    # ── 长期层：核心记忆 ─────────────────────────────────
    def read_key_memory(self) -> str:
        """读取长期记忆"""
        if not self.memory_file.exists():
            return ""
        try:
            return self.memory_file.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                return self.memory_file.read_text(encoding="gbk")
            except UnicodeDecodeError:
                return ""

    def write_key_memory(self, content: str):
        """写入长期记忆（覆盖）"""
        self.memory_file.write_text(content.strip()+"", encoding="utf-8")

    def append_key_memory(self, content: str):
        """追加内容到长期记忆"""
        current = self.read_key_memory()
        new_content = current.rstrip() + "\n" + content.strip()
        self.memory_file.write_text(new_content, encoding="utf-8")


    # ── 归档功能 ─────────────────────────────────────────
    def append_compact_marker(self) -> None:
        """添加归档标记，标记之前的历史已压缩"""
        row = {
            "time": datetime.now(UTC8).isoformat(timespec="seconds"),
            "type": "compact_event"
        }
        with self.history_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def load_unarchived_history(self) -> list:
        """加载未归档的历史记录（最后一个 compact_event 之后的对话）"""
        if not self.history_file.exists():
            return []
        rows = []
        try:
            with self.history_file.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except UnicodeDecodeError:
            # 如果 UTF-8 失败，尝试 GBK
            try:
                with self.history_file.open("r", encoding="gbk") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            rows.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
            except UnicodeDecodeError:
                print(f"警告: 无法读取历史文件 {self.history_file}")
                return []
        # 找到最后一个归档标记
        last_marker = -1
        for i, row in enumerate(rows):
            if row.get("type") == "compact_event":
                last_marker = i
        # 返回归档标记之后的对话
        return [
            {"role": r["role"], "content": r["content"]}
            for r in rows[last_marker + 1:]
            if "role" in r and "content" in r
        ]

    def summarize_and_compact(self, history: list) -> None:
        from agent_hemo.core.llm_client import HelloAgentsLLM
        """把旧对话压缩成摘要，保留System + 摘要 + 最近N条"""

        # 1. 找出要压缩的部分(system 不动，最近 N 条不动)
        system_msg = history[0]
        recent_msgs = history[-COMPACT_RECENT_MESSAGES:]
        to_summarize = history[1:-COMPACT_RECENT_MESSAGES]

        # 不足4条
        if not to_summarize:
            return history

        # 2. 拼成文本让LLM摘要
        text = "\n".join([f"{m['role']}: {m['content']}" for m in to_summarize])
        summary_prompt = [
            {"role": "system", "content": "请用中文简要总结以下对话的关键信息，保留用户偏好、任务进度、重要结论。"},
            {"role": "user", "content": text},
        ]
        summary = HelloAgentsLLM().invoke(messages=summary_prompt)
        if hasattr(summary, 'content'):
            if isinstance(summary.content, list):
                # 如果是列表格式，提取文本内容
                reply = "".join([item.get("text", "") for item in summary.content if item.get("type") == "text"])
            else:
                reply = summary.content
        else:
            reply = str(summary)
        
        # 3.写进今日情景记忆
        self.append_episode(f"**对话摘要**： {reply}")
        self.append_compact_marker()

        # 4. 返回压缩后的history
        return [system_msg, {"role": "user", "content": f"[此前对话摘要] \n {reply}"}, *recent_msgs]