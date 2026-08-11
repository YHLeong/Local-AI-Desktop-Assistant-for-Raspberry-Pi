import json
import requests
from PySide6.QtCore import QObject, Signal, Slot
from core.config import OLLAMA_BASE_URL

class OllamaClient:
    def __init__(self, base_url=OLLAMA_BASE_URL):
        self.base_url = base_url.rstrip("/")

    def list_models(self):
        r = requests.get(f"{self.base_url}/api/tags", timeout=5)
        r.raise_for_status()
        return [m["name"] for m in r.json().get("models", [])]

    def is_online(self):
        try:
            requests.get(f"{self.base_url}/api/tags", timeout=2).raise_for_status()
            return True
        except requests.RequestException:
            return False

class ChatWorker(QObject):
    chunk = Signal(str)
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, model, messages, base_url=OLLAMA_BASE_URL):
        super().__init__()
        self.model = model
        self.messages = messages
        self.base_url = base_url.rstrip("/")
        self._stop = False

    @Slot()
    def run(self):
        payload = {"model": self.model, "messages": self.messages, "stream": True}
        full = ""
        try:
            with requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                stream=True,
                timeout=(10, 600),
            ) as r:
                r.raise_for_status()
                for line in r.iter_lines(decode_unicode=True):
                    if self._stop:
                        break
                    if not line:
                        continue
                    data = json.loads(line)
                    text = data.get("message", {}).get("content", "")
                    if text:
                        full += text
                        self.chunk.emit(text)
                    if data.get("done"):
                        break
            self.finished.emit(full)
        except Exception as e:
            self.error.emit(str(e))

    def stop(self):
        self._stop = True
