import json
import time
from pathlib import Path
from core.config import CHATS_DIR, SYSTEM_PROMPT

class ChatManager:
    def __init__(self):
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.current_file = None

    def new_chat(self):
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.current_file = None

    def add_user(self, text):
        self.messages.append({"role": "user", "content": text})

    def add_assistant(self, text):
        self.messages.append({"role": "assistant", "content": text})

    def visible_messages(self):
        return [m for m in self.messages if m["role"] != "system"]

    def save(self):
        if len(self.messages) <= 1:
            return
        if self.current_file is None:
            self.current_file = CHATS_DIR / f"chat_{int(time.time())}.json"
        self.current_file.write_text(
            json.dumps({"messages": self.messages}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def list_chats(self):
        return sorted(CHATS_DIR.glob("chat_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)

    def load(self, path):
        path = Path(path)
        self.messages = json.loads(path.read_text(encoding="utf-8"))["messages"]
        self.current_file = path
