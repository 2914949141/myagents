import uuid
from threading import Lock

from agent_hemo.agent_loop import AgentLoop

class SessionManager:
    """第一版：进程内内存会话, 重启后丢失"""

    def __init__(self):
        self._sessions: dict[str, AgentLoop] = {}
        self._lock = Lock()

    def get_or_create(self, session_id: str | None) -> tuple[str, AgentLoop]:
        with self._lock:
            if session_id and session_id in self._sessions:
                return session_id, self._sessions[session_id]
            
            new_id = session_id or str(uuid.uuid4())
            loop = AgentLoop()
            self._sessions[new_id] = loop
            return new_id, loop
    def delete(self, session_id: str):
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

session_manager = SessionManager()