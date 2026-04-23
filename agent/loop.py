from __future__ import annotations
import os
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from .compactor import Compactor
from .context import ContextBuilder
from .memory import MemoryStore
from .runner import AgentRunner
from .skills import SkillsLoader
from .telemetry import TokenTracker
from .tools import (
    LoadSkill, RunCommand, ToolRegistry, WebFetch,
    ReadFileTool, WriteFileTool, EditFileTool, GlobTool, GrepTool,
)


class AgentLoop:
    def __init__(self, root: Path | None = None,
                 model: str = "claude-haiku-4-5-20251001"):
        load_dotenv()
        self.root = root or Path(__file__).parent.parent

        client = anthropic.Anthropic(
            api_key=os.environ["ANTHROPIC_API_KEY"],
            base_url=os.environ.get("ANTHROPIC_BASE_URL"),
        )

        self.memory = MemoryStore(
            memory_dir=self.root / "memory",
            user_file=self.root / "templates" / "USER.md",
        )
        token_tracker = TokenTracker(self.root / "memory" / "tokens.jsonl")
        compactor = Compactor(client, model, self.memory)

        skills = SkillsLoader(self.root / "skills")
        ctx = ContextBuilder(self.root / "templates", skills, memory=self.memory)

        workspace = self.root
        registry = ToolRegistry()
        registry.register(RunCommand())
        registry.register(WebFetch())
        registry.register(LoadSkill(skills))
        registry.register(ReadFileTool(workspace))
        registry.register(WriteFileTool(workspace))
        registry.register(EditFileTool(workspace))
        registry.register(GlobTool(workspace))
        registry.register(GrepTool(workspace))

        unarchived = self.memory.load_unarchived_history()
        if len(unarchived) >= 2:
            print(f"[Startup: found {len(unarchived)} unarchived turns, compacting...]")
            try:
                compactor.compact_startup(unarchived)
            except Exception as exc:
                print(f"[warning] startup compaction failed: {exc}", file=sys.stderr)

        system_prompt = ctx.build_system_prompt()
        print(f"[System Prompt]\n{system_prompt}\n{'='*60}\n")

        self.runner = AgentRunner(
            client=client,
            model=model,
            registry=registry,
            system_prompt=system_prompt,
            memory_store=self.memory,
            token_tracker=token_tracker,
            compactor=compactor,
        )
        self.history: list = []

    def run(self) -> None:
        while True:
            user_input = input("You🫅 : ")
            self.history.append({"role": "user", "content": user_input})
            self.memory.append_history("user", user_input)
            reply = self.runner.step(self.history)
            print(f"大内总管🧟\u200d♂️: {reply}\n")
