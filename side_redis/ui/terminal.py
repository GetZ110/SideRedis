"""Redis command console."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from side_redis.redis_client import redis_manager


class Terminal(QWidget):
    def __init__(self):
        super().__init__()
        self.cmd_history = []
        self.history_index = -1
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Output area
        self.output_widget = QWidget()
        self.output_widget.setStyleSheet("background-color: #1e1e1e;")
        output_layout = QVBoxLayout(self.output_widget)
        output_layout.setContentsMargins(5, 5, 5, 5)
        output_layout.setSpacing(2)

        self.output_labels = []
        layout.addWidget(self.output_widget, 1)

        # Input area
        input_layout = QHBoxLayout()
        input_layout.setSpacing(4)

        prompt_label = QLabel("redis>")
        prompt_label.setStyleSheet(
            "color: #569cd6; font-family: monospace; font-weight: bold;"
        )
        input_layout.addWidget(prompt_label)

        self.cmd_input = QLineEdit()
        self.cmd_input.setPlaceholderText("Enter command...")
        self.cmd_input.setStyleSheet("font-family: monospace;")
        self.cmd_input.returnPressed.connect(self._execute)
        input_layout.addWidget(self.cmd_input, 1)

        send_btn = QPushButton("Send")
        send_btn.clicked.connect(self._execute)
        input_layout.addWidget(send_btn)

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear)
        input_layout.addWidget(clear_btn)

        layout.addLayout(input_layout)

    def _execute(self):
        cmd = self.cmd_input.text().strip()
        if not cmd:
            return

        self.cmd_input.setText("")
        self.cmd_history.append(cmd)
        self.history_index = len(self.cmd_history)

        self._append_output(f"> {cmd}", "#569cd6")

        if not redis_manager.connected:
            self._append_output("Not connected to Redis", "#f44747")
            return

        try:
            result = redis_manager.execute(redis_manager.client.execute_command, cmd)
            formatted = self._format_result(result)
            self._append_output(formatted, "#6a9955")
        except Exception as e:
            self._append_output(f"(error) {e}", "#f44747")

    def _append_output(self, text: str, color: str = "#d4d4d4"):
        label = QLabel(text)
        label.setStyleSheet(f"color: {color}; font-family: monospace; font-size: 12px;")
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.output_labels.append(label)
        self.output_widget.layout().addWidget(label)

    def _format_result(self, result) -> str:
        if result is None:
            return "(nil)"
        if isinstance(result, bool):
            return str(result).lower()
        if isinstance(result, (int, float)):
            return f"(integer) {result}"
        if isinstance(result, bytes):
            return result.decode("utf-8", errors="replace")
        if isinstance(result, str):
            return f'"{result}"'
        if isinstance(result, list):
            if not result:
                return "(empty list or set)"
            lines = []
            for i, item in enumerate(result, 1):
                lines.append(f"{i}) {self._format_result(item)}")
            return "\n".join(lines)
        if isinstance(result, dict):
            lines = []
            idx = 1
            for k, v in result.items():
                lines.append(f'{idx}) "{k}"')
                lines.append(f"{idx + 1}) {self._format_result(v)}")
                idx += 2
            return "\n".join(lines)
        return str(result)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Up:
            self._history_up()
            event.accept()
        elif event.key() == Qt.Key_Down:
            self._history_down()
            event.accept()
        else:
            try:
                super().keyPressEvent(event)
            except Exception:
                pass

    def _history_up(self):
        if self.cmd_history and self.history_index > 0:
            self.history_index -= 1
            self.cmd_input.setText(self.cmd_history[self.history_index])

    def _history_down(self):
        if self.history_index < len(self.cmd_history) - 1:
            self.history_index += 1
            self.cmd_input.setText(self.cmd_history[self.history_index])
        else:
            self.history_index = len(self.cmd_history)
            self.cmd_input.setText("")

    def _clear(self):
        for label in self.output_labels:
            label.deleteLater()
        self.output_labels.clear()
