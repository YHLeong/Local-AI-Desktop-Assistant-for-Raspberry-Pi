from PySide6.QtCore import QThread, QTimer, Qt, QEvent
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QMainWindow, QMessageBox, QPlainTextEdit, QPushButton, QTextBrowser,
    QVBoxLayout, QWidget
)
from core.chat_manager import ChatManager
from core.config import DEFAULT_MODEL
from core.ollama_client import ChatWorker, OllamaClient
from core.system_info import summary
from ui.theme import APP_STYLE

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PiAI")
        self.resize(1150, 760)
        self.setMinimumSize(900, 600)
        self.setStyleSheet(APP_STYLE)

        self.client = OllamaClient()
        self.chat = ChatManager()
        self.worker_thread = None
        self.worker = None
        self.current_response = ""

        self.build_ui()
        self.refresh_models()
        self.refresh_chat_list()
        self.refresh_status()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_status)
        self.timer.start(3000)

    def build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(260)
        sl = QVBoxLayout(sidebar)

        title = QLabel("PiAI")
        title.setObjectName("title")
        sl.addWidget(title)

        self.ollama_status = QLabel("Ollama: checking...")
        sl.addWidget(self.ollama_status)

        self.system_status = QLabel("")
        self.system_status.setWordWrap(True)
        sl.addWidget(self.system_status)

        new_btn = QPushButton("+ New Chat")
        new_btn.clicked.connect(self.new_chat)
        sl.addWidget(new_btn)

        sl.addWidget(QLabel("Previous chats"))
        self.chat_list = QListWidget()
        self.chat_list.itemDoubleClicked.connect(self.load_chat)
        sl.addWidget(self.chat_list, 1)

        sl.addWidget(QLabel("Model"))
        self.model_combo = QComboBox()
        sl.addWidget(self.model_combo)

        refresh_btn = QPushButton("Refresh models")
        refresh_btn.clicked.connect(self.refresh_models)
        sl.addWidget(refresh_btn)

        root_layout.addWidget(sidebar)

        main = QWidget()
        ml = QVBoxLayout(main)
        ml.setContentsMargins(24, 18, 24, 18)

        header = QHBoxLayout()
        htitle = QLabel("Local AI Assistant")
        htitle.setObjectName("title")
        header.addWidget(htitle)
        header.addStretch()

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_generation)
        header.addWidget(self.stop_btn)
        ml.addLayout(header)

        self.chat_view = QTextBrowser()
        ml.addWidget(self.chat_view, 1)

        self.input_box = QPlainTextEdit()
        self.input_box.setPlaceholderText("Message PiAI...")
        self.input_box.setMaximumHeight(130)
        self.input_box.installEventFilter(self)
        ml.addWidget(self.input_box)

        row = QHBoxLayout()
        row.addStretch()
        self.send_btn = QPushButton("Send")
        self.send_btn.setObjectName("sendButton")
        self.send_btn.clicked.connect(self.send_message)
        row.addWidget(self.send_btn)
        ml.addLayout(row)

        root_layout.addWidget(main, 1)
        self.render_chat()

    def eventFilter(self, obj, event):
        if obj is self.input_box and event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                if event.modifiers() & Qt.ShiftModifier:
                    return False
                self.send_message()
                return True
        return super().eventFilter(obj, event)

    def refresh_models(self):
        previous = self.model_combo.currentText()
        try:
            models = self.client.list_models()
        except Exception:
            models = []

        self.model_combo.clear()
        if models:
            self.model_combo.addItems(models)
            preferred = previous if previous in models else DEFAULT_MODEL
            idx = self.model_combo.findText(preferred)
            if idx >= 0:
                self.model_combo.setCurrentIndex(idx)
        else:
            self.model_combo.addItem(DEFAULT_MODEL)

    def refresh_status(self):
        online = self.client.is_online()
        self.ollama_status.setText("● Ollama online" if online else "● Ollama offline")
        try:
            s = summary()
            temp = f"{s['temp']:.1f}°C" if s["temp"] is not None else "N/A"
            self.system_status.setText(
                f"{s['hostname']}\nCPU {s['cpu']:.0f}%   RAM {s['ram']:.0f}%\n"
                f"Disk {s['disk']:.0f}%   Temp {temp}"
            )
        except Exception:
            pass

    def refresh_chat_list(self):
        self.chat_list.clear()
        for path in self.chat.list_chats():
            item = QListWidgetItem(path.stem.replace("chat_", "Chat "))
            item.setData(Qt.UserRole, str(path))
            self.chat_list.addItem(item)

    def load_chat(self, item):
        try:
            self.chat.load(item.data(Qt.UserRole))
            self.render_chat()
        except Exception as e:
            QMessageBox.critical(self, "Load failed", str(e))

    def new_chat(self):
        if self.worker_thread is not None:
            return
        self.chat.new_chat()
        self.render_chat()

    def send_message(self):
        if self.worker_thread is not None:
            return
        text = self.input_box.toPlainText().strip()
        if not text:
            return

        model = self.model_combo.currentText().strip()
        self.chat.add_user(text)
        self.input_box.clear()
        self.current_response = ""
        self.render_chat(True, "")

        self.send_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.model_combo.setEnabled(False)

        self.worker_thread = QThread(self)
        self.worker = ChatWorker(model, list(self.chat.messages))
        self.worker.moveToThread(self.worker_thread)

        self.worker_thread.started.connect(self.worker.run)
        self.worker.chunk.connect(self.on_chunk)
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.error.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self.cleanup_worker)
        self.worker_thread.start()

    def on_chunk(self, text):
        self.current_response += text
        self.render_chat(True, self.current_response)

    def on_finished(self, full_text):
        if full_text.strip():
            self.chat.add_assistant(full_text)
        self.chat.save()
        self.render_chat()
        self.refresh_chat_list()

    def on_error(self, message):
        QMessageBox.critical(self, "Ollama error", message)

    def cleanup_worker(self):
        self.worker = None
        self.worker_thread.deleteLater()
        self.worker_thread = None
        self.send_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.model_combo.setEnabled(True)

    def stop_generation(self):
        if self.worker:
            self.worker.stop()

    def render_chat(self, live=False, live_text=""):
        html = """
        <html><head><style>
        body { font-family: Arial; color:#e7e7e7; background:#0f1115; font-size:15px; }
        .msg { margin:10px 0 18px 0; padding:12px 14px; border-radius:10px; }
        .user { background:#242a33; }
        .assistant { background:#151920; }
        .role { font-weight:bold; margin-bottom:7px; }
        pre { background:#090b0f; border:1px solid #303642; padding:10px; border-radius:7px; white-space:pre-wrap; }
        </style></head><body>
        """
        for m in self.chat.visible_messages():
            role = m["role"]
            label = "You" if role == "user" else "PiAI"
            css = "user" if role == "user" else "assistant"
            content = self.escape(m["content"]).replace("\n", "<br>")
            html += f'<div class="msg {css}"><div class="role">{label}</div>{content}</div>'

        if live:
            content = self.escape(live_text or "Thinking...").replace("\n", "<br>")
            html += f'<div class="msg assistant"><div class="role">PiAI</div>{content}</div>'

        html += "</body></html>"
        self.chat_view.setHtml(html)
        c = self.chat_view.textCursor()
        c.movePosition(QTextCursor.End)
        self.chat_view.setTextCursor(c)

    @staticmethod
    def escape(text):
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
