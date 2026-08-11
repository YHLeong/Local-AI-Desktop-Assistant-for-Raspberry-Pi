from pathlib import Path

OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "gemma3:1b"

BASE_DIR = Path(__file__).resolve().parent.parent
CHATS_DIR = BASE_DIR / "chats"
CHATS_DIR.mkdir(exist_ok=True)

SYSTEM_PROMPT = (
    "You are PiAI, a concise local AI assistant running on a Raspberry Pi 5. "
    "Give technically accurate answers and prefer complete commands/code."
)
