from myagents.utils.token_utils import TokenTracker, parse_usage
from types import SimpleNamespace

def test_parse_usage_from_object():
    usage = SimpleNamespace(
        prompt_tokens=100,
        completion_tokens=200,
        total_tokens=300,
    )
    result = parse_usage(usage)
    assert result == {
        "prompt_tokens": 100,
        "completion_tokens": 200,
        "total_tokens": 300,
    }

def test_parse_usage_none():
    result = parse_usage(None)
    assert result["total_tokens"] == 0

def test_token_tracker_accumulates():
    tracker = TokenTracker()
    tracker.add({"prompt_tokens": 100, "completion_tokens": 200, "total_tokens": 300})
    tracker.add({"prompt_tokens": 100, "completion_tokens": 200, "total_tokens": 300})

    snap = tracker.snapshot()
    assert snap["prompt_tokens"] == 200
    assert snap["completion_tokens"] == 400
    assert snap["total_tokens"] == 600
    assert snap["call_count"] == 2