from __future__ import annotations

from .tools.registry import ToolRegistry


class AgentRunner:
    def __init__(
        self,
        client,
        model: str,
        registry: ToolRegistry,
        system_prompt: str,
        max_tokens: int = 20000,
        memory_store=None,
        token_tracker=None,
        compactor=None,
        max_context: int = 200_000,
        compact_threshold: float = 0.7,
        max_turns: int | None = None,
    ):
        self.client = client
        self.model = model
        self.registry = registry
        self.system_prompt = system_prompt
        self.max_tokens = max_tokens
        self.memory_store = memory_store
        self.token_tracker = token_tracker
        self.compactor = compactor
        self.max_context = max_context
        self.compact_threshold = compact_threshold
        self.max_turns = max_turns

    def step(self, history: list) -> str:
        """Run one full turn (user→...→final-text). Mutates `history` in place."""
        turns = 0
        while True:
            if self.max_turns is not None and turns >= self.max_turns:
                return f"（达到 max_turns={self.max_turns} 上限, 未办妥；history 中已有部分进展）"
            turns += 1
            message = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=self.system_prompt,
                tools=self.registry.get_definitions(),
                messages=history,
            )
            if self.token_tracker:
                self.token_tracker.record(self.model, message.usage)
            history.append({"role": "assistant", "content": message.content})

            if message.stop_reason != "tool_use":
                reply = next(b.text for b in message.content if b.type == "text")
                if self.memory_store:
                    self.memory_store.append_history("assistant", reply)
                self._maybe_compact(history)
                return reply

            tool_results = []
            for block in message.content:
                if block.type != "tool_use":
                    continue
                content = self.registry.execute(block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": content,
                })

            history.append({"role": "user", "content": tool_results})

    def _maybe_compact(self, history: list) -> None:
        if not (self.compactor and self.token_tracker):
            return
        if not self.token_tracker.should_compact(self.max_context, self.compact_threshold):
            return
        history[:] = self.compactor.compact(history)
