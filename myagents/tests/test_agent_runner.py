from unittest.mock import MagicMock
from myagents.agent_runner import AgentRunner

def test_runner_returns_reply_when_no_tools():
    mock_llm = MagicMock()
    mock_message = MagicMock()
    mock_message.tool_calls = []
    mock_message.content = "你好我是小杜"
    mock_message.usage = None
    mock_llm.invoke.return_value = mock_message

    runner = AgentRunner(mock_llm)
    history = [{"role": "user", "content": "你好"}]
    result = runner.run(history)

    assert result == "你好我是小杜"
    assert mock_llm.invoke.called