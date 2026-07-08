"""LLM-as-Judge：对 Agent 单题回答打分。"""

from __future__ import annotations

import json
import re
from typing import Any

from agent_hemo.core.llm_client import HelloAgentsLLM

PASS_OVERALL_THRESHOLD = 4


def extract_llm_text(message) -> str:
    if message is None:
        return ""
    content = getattr(message, "content", "")
    if isinstance(content, list):
        return "".join(
            item.get("text", "")
            for item in content
            if item.get("type") == "text"
        )
    return content or ""


def parse_judge_json(text: str) -> dict[str, Any]:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        text = text[start : end + 1]
    return json.loads(text)


def _category_rubric(category: str) -> str:
    if category == "knowledge":
        return (
            "这是业务知识问答。重点：是否基于引用来源作答、关键数字/条款是否正确、"
            "是否注明来源、个体判定是否提醒「以现场健康征询和医师判定为准」。"
        )
    if category == "alert":
        return "这是临期血浆查询。重点：是否基于工具结果回答，不要编造袋数或站点。"
    if category == "report":
        return "这是报表生成。重点：是否说明工具执行结果（成功/文件不存在等），不要假装已生成。"
    if category == "chitchat":
        return "这是寒暄。简短友好即可，不应调用业务工具。"
    if category == "negative":
        return (
            "这是知识库外问题。必须先检索；若无相关内容，应明确说「知识库中未找到」，"
            "严禁编造量子计算机等领域外长篇内容。"
        )
    return "按血站助手通用标准评判。"


def build_judge_messages(
    case: dict,
    reply: str,
    sources: list[str],
    tools_called: list[str],
) -> list[dict[str, str]]:
    reference = case.get("reference_answer") or "（未提供参考答案，请依据引用来源与常识判断）"
    rubric = _category_rubric(case.get("category", ""))

    user_content = f"""请评测血站智能助手的一次回答。

【用户问题】
{case["query"]}

【题目类别】
{case.get("category", "")}

【评测说明】
{rubric}

【参考答案要点】（可能不完整，仅供参考）
{reference}

【Agent 实际调用的工具】
{tools_called or "（无）"}

【引用来源】
{sources or "（无）"}

【Agent 回答】
{reply}

请只输出一个 JSON 对象，不要其他文字：
{{
  "correctness": 1-5,
  "groundedness": 1-5,
  "completeness": 1-5,
  "overall": 1-5,
  "pass": true或false,
  "reason": "一句话说明"
}}

打分标准：
- 5 分：完全正确、有依据、可执行
- 3 分：大体可用但有遗漏或依据不足
- 1 分：明显错误、编造、或严重跑题
- pass：overall>=4 且无编造、且符合该类题目要求时为 true
"""

    return [
        {
            "role": "system",
            "content": "你是严谨的血站业务评测员，只输出合法 JSON，不要 markdown。",
        },
        {"role": "user", "content": user_content},
    ]


def judge_case(
    llm: HelloAgentsLLM,
    case: dict,
    reply: str,
    sources: list[str],
    tools_called: list[str],
) -> dict[str, Any]:
    messages = build_judge_messages(case, reply, sources, tools_called)
    message = llm.invoke(messages=messages, temperature=0, tools=[])
    raw = extract_llm_text(message)

    try:
        data = parse_judge_json(raw)
    except (json.JSONDecodeError, ValueError) as e:
        return {
            "judge_ok": False,
            "judge_error": f"JSON 解析失败: {e}",
            "judge_raw": raw[:500],
            "correctness": 0,
            "groundedness": 0,
            "completeness": 0,
            "overall": 0,
            "pass": False,
            "reason": "Judge 输出无法解析",
        }

    overall = int(data.get("overall", 0))
    passed = bool(data.get("pass", overall >= PASS_OVERALL_THRESHOLD))

    return {
        "judge_ok": True,
        "correctness": int(data.get("correctness", 0)),
        "groundedness": int(data.get("groundedness", 0)),
        "completeness": int(data.get("completeness", 0)),
        "overall": overall,
        "pass": passed,
        "reason": str(data.get("reason", "")),
    }