"""对话记忆 - 存储和检索与每个人的对话历史"""

import json
import os
from datetime import datetime
from pydantic import BaseModel, Field


class Message(BaseModel):
    """单条对话消息"""
    role: str  # user / assistant
    content: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    metadata: dict = Field(default_factory=dict)


class ConversationSession(BaseModel):
    """一次对话会话"""
    person_name: str
    messages: list[Message] = Field(default_factory=list)
    summary: str = ""
    started_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    ended_at: str = ""


class ConversationStore:
    """对话记忆存储"""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.file = os.path.join(data_dir, "conversations.json")
        os.makedirs(data_dir, exist_ok=True)
        self._sessions: list[ConversationSession] = []
        self._current: dict[str, ConversationSession] = {}
        self._load()

    def _load(self):
        if os.path.exists(self.file):
            with open(self.file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._sessions = [ConversationSession(**s) for s in data]

    def _save(self):
        all_sessions = self._sessions.copy()
        for session in self._current.values():
            all_sessions.append(session)
        with open(self.file, "w", encoding="utf-8") as f:
            json.dump([s.model_dump() for s in all_sessions],
                      f, ensure_ascii=False, indent=2)

    def start_session(self, person_name: str) -> ConversationSession:
        if person_name in self._current:
            return self._current[person_name]
        session = ConversationSession(person_name=person_name)
        self._current[person_name] = session
        return session

    def add_message(self, person_name: str, role: str, content: str,
                    **metadata) -> Message:
        session = self._current.get(person_name)
        if not session:
            session = self.start_session(person_name)
        msg = Message(role=role, content=content, metadata=metadata)
        session.messages.append(msg)
        return msg

    def end_session(self, person_name: str, summary: str = ""):
        session = self._current.pop(person_name, None)
        if session:
            session.ended_at = datetime.now().isoformat()
            session.summary = summary
            self._sessions.append(session)
            self._save()

    def get_recent(self, person_name: str, limit: int = 10) -> list[Message]:
        """获取某人最近的对话消息"""
        messages = []
        # 当前会话
        current = self._current.get(person_name)
        if current:
            messages.extend(current.messages)
        # 历史会话
        for session in reversed(self._sessions):
            if session.person_name == person_name:
                messages.extend(session.messages)
        return messages[-limit:]

    def get_context(self, person_name: str, limit: int = 20) -> str:
        """获取对话上下文，用于喂给 AI"""
        messages = self.get_recent(person_name, limit)
        if not messages:
            return f"（与 {person_name} 暂无对话记录）"
        lines = []
        for msg in messages:
            role = "用户" if msg.role == "user" else "AI"
            lines.append(f"[{role}] {msg.content}")
        return "\n".join(lines)

    def get_summaries(self, person_name: str) -> list[str]:
        return [s.summary for s in self._sessions
                if s.person_name == person_name and s.summary]

    def search(self, keyword: str) -> list[tuple[str, Message]]:
        results = []
        for session in self._sessions:
            for msg in session.messages:
                if keyword.lower() in msg.content.lower():
                    results.append((session.person_name, msg))
        current_session = self._current.get("")
        for name, session in self._current.items():
            for msg in session.messages:
                if keyword.lower() in msg.content.lower():
                    results.append((name, msg))
        return results
