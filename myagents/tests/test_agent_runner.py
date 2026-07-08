from unittest.mock import MagicMock
from agent_hemo.agent_runner import AgentRunner

def test_runner_returns_reply_when_no_tools():
    mock_llm = MagicMock()
    mock_message = MagicMock()
    mock_message.tool_calls = []
    mock_message.content = "你好我是小杜"
    mock_message.usage = None
    mock_llm.invoke.return_value = mock_message

    runner = AgentRunner(mock_llm)
    history = [{"role": "user", "content": "你好"}]
    result, sources = runner.run(history)

    assert result == "你好我是小杜"
    assert sources == []
    assert mock_llm.invoke.called

def test_look_like_failure():
    runner = AgentRunner(MagicMock())
    ok = "报告已成功生成，淘汰率5.5%, 各站点统计如下"
    assert not runner._look_like_failure(ok)
    failure = "错误：工具执行失败"
    assert runner._look_like_failure(failure)
    failure = "抱歉, 知识库没有找到"
    assert runner._look_like_failure(failure)
    failure = "安全限制："
    assert runner._look_like_failure(failure)
    failure = "错误：工具执行失败"
    assert runner._look_like_failure(failure)
    failure = "抱歉, 知识库没有找到"
    assert runner._look_like_failure(failure)

def test_look_like_failure_flags_tool_error():
    runner = AgentRunner(MagicMock())
    runner._last_run_had_tool_error = True
    assert runner._look_like_failure("任意内容") is True
    