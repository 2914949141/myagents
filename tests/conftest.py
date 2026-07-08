import json
from types import SimpleNamespace


def make_tool_call(name: str, arguments: dict):
    """构造一个假的tool_call对象，供工具execute()使用"""
    return SimpleNamespace(
        id="test-call-1",
        function=SimpleNamespace(
            name=name,
            arguments=json.dumps(arguments, ensure_ascii=False),
        ),
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: 需要网络和 .env 配置的集成测试"
    )
