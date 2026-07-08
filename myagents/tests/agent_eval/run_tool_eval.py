"""Agent 工具路由评测（Layer 2）：量化工具选对没。"""
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

def load_cases() -> list[dict]:
    rows = []
    with CASES_FILE.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows

def extract_tool_calls(history: list[dict]) -> list[str]:
    names = []
    for msg in history:
        if msg.get("role") == "assistant":
            for tc in msg.get("tool_calls") or []:
                names.append(tc["function"]["name"])
    return names

def score_case(case: dict, tools: list[str], reply: str, sources: list[str]) -> dict:
    expected = case.get("expected_tools") or []
    forbidden = case.get("forbidden_tools") or []
    max_rag = case.get("max_rag_calls", 2)
    must_any = case.get("must_include_any", [])

    tool_ok = all(t in tools for t in expected)
    forbidden_hit = any(t in tools for t in forbidden)
    over_rag = tools.count("rag_search") > max_rag
    must_ok = (not must_any) or any(m in reply for m in must_any)
    passed = tool_ok and not forbidden_hit and not over_rag and must_ok

    return {
        "id": case["id"],
        "query": case["query"],
        "category": case.get("category", ""),
        "tools_called": tools,
        "rag_calls": tools.count("rag_search"),
        "tool_ok": tool_ok,
        "forbidden_hit": forbidden_hit,
        "over_rag": over_rag,
        "must_ok": must_ok,
        "passed": passed,
        "reply_preview": reply[:300],
        "sources": sources,
    }

def run_eval(cases: list[dict]) -> list[dict]:
    loop = AgentLoop()
    system = loop.history[0]
    runner = loop.agent_runner
    results = []
    
    for i, case in enumerate(cases, 1):
        print(f"[{i}/{len(cases)}] {case['id']}: {case['query']}")
        history = [system, {"role": "user", "content": case["query"]}]
        reply, sources = runner.run_with_relexion(history, quiet=True)
        tools = extract_tool_calls(history)
        row = score_case(case, tools, reply, sources)
        results.append(row)
        mark = "PASS" if row["passed"] else "FAIL"
        print(f"  {mark}  tools={tools}  rag={row['rag_calls']}")
        if not row["passed"]:
            if not row["tool_ok"]:
                print(f"       缺期望工具: {case.get('expected_tools')}")
            if row["forbidden_hit"]:
                print(f"       误调禁止工具: {case.get('forbidden_tools')}")
            if row["over_rag"]:
                print(f"       rag 超过 {case.get('max_rag_calls', 2)} 次")
            if not row["must_ok"]:
                print(f"       回复未包含: {case.get('must_include_any')}")
        print()
    return results


def summarize(results: list[dict]) -> dict:
    n = len(results) or 1
    knowledge = [r for r in results if r["category"] == "knowledge"]
    return {
        "total": len(results),
        "passed": sum(1 for r in results if r["passed"]),
        "pass_rate": sum(1 for r in results if r["passed"]) / n,
        "tool_accuracy": sum(1 for r in results if r["tool_ok"]) / n,
        "forbidden_rate": sum(1 for r in results if r["forbidden_hit"]) / n,
        "over_rag_rate": sum(1 for r in results if r["over_rag"]) / n,
        "avg_rag_calls_on_knowledge": (
            sum(r["rag_calls"] for r in knowledge) / len(knowledge) if knowledge else 0.0
        ),
    }
def main() -> None:
    cases = load_cases()
    print(f"加载 {len(cases)} 道 Agent 用例\n")
    print("注意：会调用真实 LLM，请确认 .env 里 LLM_API_KEY / LLM_BASE_URL 已配置\n")
    results = run_eval(cases)
    summary = summarize(results)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / f"{datetime.now().strftime('%Y-%m-%d_%H%M%S')}_tool_eval.json"
    report_path.write_text(
        json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("=== 汇总 ===")
    print(f"通过: {summary['passed']}/{summary['total']} ({summary['pass_rate']:.1%})")
    print(f"工具准确率: {summary['tool_accuracy']:.1%}")
    print(f"误调禁止工具率: {summary['forbidden_rate']:.1%}")
    print(f"过度 rag 率: {summary['over_rag_rate']:.1%}")
    print(f"知识题平均 rag 次数: {summary['avg_rag_calls_on_knowledge']:.2f}")
    print(f"报告已写入: {report_path}")


if __name__ == "__main__":
    main()