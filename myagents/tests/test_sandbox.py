import pytest
from agent_hemo.settings import PROJECT_ROOT
from agent_hemo.utils.sandbox import is_path_allowed, validate_command

class TestIsPathAllowed:
    def test_allow_inside_project(self):
        path = str(PROJECT_ROOT / "README.md")
        assert is_path_allowed(path) is True
    
    def test_block_windows_system_path(self):
        assert is_path_allowed("C:\\Windows\\System32\\cmd.exe") is False
    
    
    def test_allow_relative_path(self):
        assert is_path_allowed("./agent_loop.py") is True

class TestValidateCommand:
    def test_allow_dir(self):
        allowed, _ = validate_command("dir")
        assert allowed is True
    def test_allow_curl(self):
        allowed, _ = validate_command('curl -s "wttr.in/Beijing"')
        assert allowed is True
    def test_block_type_removed_from_whitelist(self):
        allowed, reason = validate_command(r"type C:\Windows\System32\drivers\etc\hosts")
        assert allowed is False
        assert "白名单" in reason
    def test_block_del(self):
        allowed, reason = validate_command("del /s /q *")
        assert allowed is False
    def test_block_unknown_command(self):
        allowed, _ = validate_command("node script.js")
        assert allowed is False