"""Agent 端到端评测：工具路由 + LLM-as-Judge。"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
CASES_FILE = EVAL_DIR / "cases.jsonl"
REPORTS_DIR = EVAL_DIR / "reports"

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agent_hemo.agent_loop import AgentLoop
from agent_hemo.core.llm_client import HelloAgentsLLM
from tests.agent_eval.judge import judge_case
from tests.agent_eval.run_tool_eval import (
    extract_tool_calls,
    load_cases,
    score_case,
    summarize as summarize_tools,
)


def run_e2e(cases: list[dict]) -> list[dict]:
    loop = AgentLoop()
    system = loop.history[0]
    runner = loop.agent_runner
    judge_llm = HelloAgentsLLM()
    results = []

    for i, case in enumerate(cases, 1):
        if case["category"] != "knowledge": 
            continue
        print(f"[{i}/{len(cases)}] {case['id']}: {case['query']}")
        history = [system, {"role": "user", "content": case["query"]}]
        reply, sources = runner.run_with_relexion(history, quiet=True)
        tools = extract_tool_calls(history)

        tool_row = score_case(case, tools, reply, sources)
        tool_row["reply"] = reply

        print(f"  工具层: {'PASS' if tool_row['passed'] else 'FAIL'}  tools={tools}")
        print("  Judge 评分中...")
        judge_row = judge_case(judge_llm, case, reply, sources, tools)
        tool_row.update(judge_row)

        e2e_pass = tool_row["passed"] and judge_row.get("pass", False)
        tool_row["e2e_pass"] = e2e_pass
        results.append(tool_row)

        print(
            f"  Judge: overall={judge_row.get('overall')} "
            f"pass={judge_row.get('pass')} "
            f"reason={judge_row.get('reason')}"
        )
        print(f"  端到端: {'PASS' if e2e_pass else 'FAIL'}\n")

    return results


def summarize_e2e(results: list[dict]) -> dict:
    tool_summary = summarize_tools(results)
    n = len(results) or 1
    judged = [r for r in results if r.get("judge_ok")]
    return {
        **tool_summary,
        "judge_pass_rate": sum(1 for r in results if r.get("pass")) / n,
        "e2e_pass_rate": sum(1 for r in results if r.get("e2e_pass")) / n,
        "avg_overall": (
            sum(r.get("overall", 0) for r in judged) / len(judged) if judged else 0.0
        ),
        "avg_groundedness": (
            sum(r.get("groundedness", 0) for r in judged) / len(judged) if judged else 0.0
        ),
        "judge_parse_failures": sum(1 for r in results if not r.get("judge_ok")),
    }


def main() -> None:
    cases = load_cases()
    print(f"加载 {len(cases)} 道用例\n")
    print("将调用真实 Agent LLM + Judge LLM（约 2× 题数 次 API）\n")

    results = run_e2e(cases)
    summary = summarize_e2e(results)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / f"{datetime.now().strftime('%Y-%m-%d_%H%M%S')}_e2e_eval.json"
    report_path.write_text(
        json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("=== 汇总 ===")
    print(f"工具层通过: {summary['passed']}/{summary['total']} ({summary['pass_rate']:.1%})")
    print(f"Judge 通过: {summary['judge_pass_rate']:.1%}")
    print(f"端到端通过: {summary['e2e_pass_rate']:.1%}")
    print(f"平均 overall: {summary['avg_overall']:.2f}")
    print(f"平均 groundedness: {summary['avg_groundedness']:.2f}")
    print(f"报告: {report_path}")


if __name__ == "__main__":
    main()