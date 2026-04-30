from __future__ import annotations
from pathlib import Path

from .spec import SubagentSpec


# 工具白名单写在代码里, 不放模板中 —— 安全设置不应被无意修改。
# 模板里只写身份/口吻/职责文案。
_BUILTIN_SPECS: dict[str, dict] = {
    "researcher": {
        "description": (
            "研究型小太监 (职责只读)。适合派去查资料、读多个文件、grep 大范围、"
            "抓网页或调搜索 API 后汇总 —— 按职责约束不应修改东西，但允许"
            "用 run_command 跑只读命令 (curl / find / jq 等)。"
        ),
        "tool_names": (
            "load_skill", "web_fetch", "run_command",
            "read_file", "glob", "grep",
        ),
        "max_turns": 15,
    },
    "general": {
        "description": (
            "通用小太监。可读可写可执行命令, 适合派去办需要动手"
            "(写文件 / 跑命令 / 多步操作) 的独立差事。"
        ),
        "tool_names": (
            "run_command", "web_fetch", "load_skill",
            "read_file", "write_file", "edit_file", "glob", "grep",
        ),
        "max_turns": 20,
    },
}

_DEFAULT_PROMPT = (
    "你是奉总管之命专办一件差事的小太监。\n"
    "- 不必使用'奉天承运皇帝诏曰'前缀, 那是总管对皇上的礼数。\n"
    "- 用工具尽快把差事办妥, 最后用一段简短中文向总管回禀。\n"
    "- 只回禀结论与关键信息, 不要复述每一步细节。\n"
    "- 你不能再派遣其他小太监, 所有差事自己跑工具完成。"
)


class SubagentRegistry:
    """从 templates/subagents/{name}.md 读取 system prompt, 与代码内置的
    工具白名单 / max_turns 配置合并, 构造 SubagentSpec。

    若提供 skills_loader, 在子代理白名单含 load_skill 时, 把 skills 摘要
    注入到 system prompt 末尾, 让子代理知道有哪些技能可加载。"""

    def __init__(self, templates_dir: Path, skills_loader=None):
        self.templates_dir = Path(templates_dir)
        self._skills_loader = skills_loader
        self._specs: dict[str, SubagentSpec] = {}
        self._load_all()

    def _load_all(self) -> None:
        for name, cfg in _BUILTIN_SPECS.items():
            prompt_file = self.templates_dir / f"{name}.md"
            if prompt_file.exists():
                system_prompt = prompt_file.read_text().strip()
            else:
                system_prompt = _DEFAULT_PROMPT

            if self._skills_loader and "load_skill" in cfg["tool_names"]:
                summary = self._skills_loader.build_skills_summary()
                if summary:
                    system_prompt += (
                        "\n\n## 可加载的技能 (load_skill)\n\n"
                        f"{summary}\n\n"
                        "遇到对应专题时, 先调 load_skill 把技能内容拉进上下文。"
                    )

            self._specs[name] = SubagentSpec(
                name=name,
                description=cfg["description"],
                system_prompt=system_prompt,
                tool_names=tuple(cfg["tool_names"]),
                max_turns=cfg["max_turns"],
            )

    def get(self, name: str) -> SubagentSpec | None:
        return self._specs.get(name)

    def names(self) -> list[str]:
        return sorted(self._specs.keys())

    def describe(self) -> str:
        """给主 agent 工具的 description 用 —— 列出所有可用 subagent。"""
        return "\n".join(
            f"  - {spec.name}: {spec.description}"
            for spec in self._specs.values()
        )
