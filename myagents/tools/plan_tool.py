
from myagents.tools.base_tool import BaseTool


class PlanTool(BaseTool):
    """指定plan工具 - 创建或更新当前事的 plan。"""

    name = "plan"
    description = ("创建或更新当前事的 plan。"
                "传入完整的 plan 数组（每次都是全量覆盖，而非增量）。"
                "用于：拆解多步骤任务、推进任务状态（pending → in_progress → completed）。"
                "约束：同一时间至多一个任务为 in_progress。")

    @classmethod
    def get_parameters(cls) -> dict:
        """返回参数定义"""
        return {
                "type": "object",
                "properties": {
                    "plan": {
                        "type": "array",
                        "description": "完整的 plan 列表，按执行顺序排列",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id":      {"type": "integer", "description": "序号，从 1 开始"},
                                "content": {"type": "string",  "description": "这一步要做什么"},
                                "status":  {
                                    "type": "string",
                                    "enum": ["pending", "in_progress", "completed"],
                                    "description": "状态"
                                }
                            },
                            "required": ["id", "content", "status"]
                        }
                    }
                },
                "required": ["plan"]
            }

    PLANS: list[dict] = []
    VALID_STATUS = {"pending", "in_progress", "completed"}
    STATUS_ICON = {"pending": "[ ]", "in_progress": "[~]", "completed": "[√]"}

    def execute(self, tool_call) -> str:
        import json
        args = json.loads(tool_call.function.arguments)
        plan = args.get('plan', list[dict])
        cleaned = []
        for i, t in enumerate(plan, start=1):
            content = (t.get("content") or "").strip()
            if not content:
                continue
            status = t.get("status", "pending")
            if status not in self.VALID_STATUS:
                status = "pending"
            cleaned.append({"id": t.get("id", i), "content": content, "status": status})

        in_progress = [t for t in cleaned if t["status"] == "in_progress"]
        if len(in_progress) > 1:
            return "Error: 同一时间只能有一个 in_progress 任务，请重新规划。"

        PlanTool.PLANS = cleaned
        print("\n[计划已更新]")
        print(self._read_todo(PlanTool.PLANS))
        print()

        pending = [t for t in PlanTool.PLANS if t["status"] == "pending"]
        done = [t for t in PlanTool.PLANS if t["status"] == "completed"]
        summary = f"plan updated: total={len(PlanTool.PLANS)}, completed={len(done)}, in_progress={len(in_progress)}, pending={len(pending)}"
        return summary + "\n\n当前列表：\n" + self._read_todo(PlanTool.PLANS)


    # =============TODOLIST制作============================================
    # 每项形如 {"id": 1, "content": "...", "status": "pending|in_progress|completed"}

    def _read_todo(self, todos: list[dict]) -> str:
        if not todos:
            return "当前无可办事项"
        lines = []
        for line in todos:
            icon = self.STATUS_ICON.get(line.get("status", "pending"), "[?]")
            lines.append(f"{icon} {line.get('id')}. {line.get('content')}")
        return "\n".join(lines)

