"""Key detail viewer/editor for all Redis data types."""

from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from side_redis.redis_client import redis_manager


class KeyDetail(QWidget):
    def __init__(self, on_key_deleted=None, on_key_changed=None):
        super().__init__()
        self.current_key: str | None = None
        self.on_key_deleted = on_key_deleted
        self.on_key_changed = on_key_changed
        self._initialized = False
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setAlignment(Qt.AlignTop)
        layout.addWidget(self.scroll)

        self.content_widget = QWidget()
        self.scroll.setWidget(self.content_widget)

        self.content_layout = QVBoxLayout(self.content_widget)
        self._show_empty()

    def _show_empty(self):
        # Only delete old widget if it's not the initial one
        if hasattr(self, '_initialized') and self._initialized:
            old_widget = self.content_widget
            self.content_widget = QWidget()
            self.scroll.setWidget(self.content_widget)
            self.content_layout = QVBoxLayout(self.content_widget)
            old_widget.deleteLater()
        else:
            self._initialized = True

        label = QLabel("Select a key to view its value")
        label.setStyleSheet("color: gray; font-size: 14px;")
        label.setAlignment(Qt.AlignCenter)
        self.content_layout.addWidget(label)

    def show_key(self, key: str):
        """Display details for a selected key."""
        self.current_key = key

        # Rebuild content widget to ensure clean state
        old_widget = self.content_widget
        self.content_widget = QWidget()
        self.scroll.setWidget(self.content_widget)
        self.content_layout = QVBoxLayout(self.content_widget)
        # Only delete old widget if it's not the initial one
        if self._initialized:
            try:
                old_widget.deleteLater()
            except RuntimeError:
                # Widget already deleted, ignore
                pass
        self._initialized = True

        try:
            key_type = redis_manager.get_key_type(key)
            ttl = redis_manager.get_ttl(key)
        except Exception as e:
            label = QLabel(f"Error: {e}")
            label.setStyleSheet("color: red;")
            self.content_layout.addWidget(label)
            return

        # Header
        header_layout = QHBoxLayout()

        type_badge = QLabel(key_type.upper())
        type_badge.setStyleSheet(
            f"background-color: {self._type_color(key_type)}; color: white; padding: 2px 8px; border-radius: 3px;"
        )
        header_layout.addWidget(type_badge)

        key_label = QLabel(key)
        key_label.setStyleSheet(
            "font-size: 16px; font-weight: bold; font-family: monospace;"
        )
        key_label.setWordWrap(True)
        header_layout.addWidget(key_label, 1)

        ttl_text = "No Expiry" if ttl == -1 else f"TTL: {ttl}s"
        ttl_badge = QLabel(ttl_text)
        ttl_badge.setStyleSheet(
            "border: 1px solid gray; padding: 2px 8px; border-radius: 3px;"
        )
        header_layout.addWidget(ttl_badge)

        self.content_layout.addLayout(header_layout)

        # Action buttons
        btn_layout = QHBoxLayout()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(lambda: self.show_key(key))
        btn_layout.addWidget(refresh_btn)

        ttl_btn = QPushButton("TTL")
        ttl_btn.clicked.connect(lambda: self._show_ttl_dialog(key))
        btn_layout.addWidget(ttl_btn)

        rename_btn = QPushButton("Rename")
        rename_btn.clicked.connect(lambda: self._show_rename_dialog(key))
        btn_layout.addWidget(rename_btn)

        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(lambda: self._confirm_delete(key))
        delete_btn.setStyleSheet("color: red;")
        btn_layout.addWidget(delete_btn)

        btn_layout.addStretch()
        self.content_layout.addLayout(btn_layout)

        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        self.content_layout.addWidget(separator)

        # Value display
        if key_type == "string":
            self._render_string(key)
        elif key_type == "hash":
            self._render_hash(key)
        elif key_type == "list":
            self._render_list(key)
        elif key_type == "set":
            self._render_set(key)
        elif key_type == "zset":
            self._render_zset(key)
        else:
            label = QLabel(f"Unsupported type: {key_type}")
            label.setStyleSheet("color: orange;")
            self.content_layout.addWidget(label)

    def _render_string(self, key: str):
        try:
            value = redis_manager.client.get(key)
        except Exception as e:
            label = QLabel(f"Error loading value: {e}")
            label.setStyleSheet("color: red;")
            self.content_layout.addWidget(label)
            return

        if isinstance(value, bytes):
            self._render_binary(key, value)
            return

        formatted = self._try_format_json(value)

        self.value_edit = QTextEdit(formatted)
        self.value_edit.setStyleSheet("font-family: monospace;")
        self.content_layout.addWidget(self.value_edit)

        save_btn = QPushButton("Save")
        save_btn.clicked.connect(lambda: self._save_string(key))
        self.content_layout.addWidget(save_btn)

    def _save_string(self, key: str):
        try:
            redis_manager.set_key_value(key, self.value_edit.toPlainText())
            QMessageBox.information(self, "Saved", "Value saved successfully")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error saving value: {e}")

    def _render_binary(self, key: str, data: bytes):
        label = QLabel(f"Binary data  ·  {len(data)} bytes")
        label.setStyleSheet("color: orange; font-size: 11px;")
        self.content_layout.addWidget(label)

        hex_str = self._format_hex_dump(data)
        text_preview = data.decode("utf-8", errors="replace")

        tabs = QTabWidget()
        self.content_layout.addWidget(tabs)

        hex_edit = QTextEdit(hex_str)
        hex_edit.setReadOnly(True)
        hex_edit.setStyleSheet("font-family: monospace; font-size: 11px;")
        tabs.addTab(hex_edit, "Hex")

        text_edit = QTextEdit(text_preview)
        text_edit.setReadOnly(True)
        tabs.addTab(text_edit, "Text")

        raw_repr = " ".join(f"{b:02X}" for b in data)
        raw_edit = QTextEdit(raw_repr)
        raw_edit.setReadOnly(True)
        raw_edit.setStyleSheet("font-family: monospace; font-size: 11px;")
        tabs.addTab(raw_edit, "Raw Bytes")

    def _render_hash(self, key: str):
        total_len = len(redis_manager.client.hgetall(key))
        label = QLabel(f"Total fields: {total_len}")
        label.setStyleSheet("color: gray; font-size: 11px;")
        self.content_layout.addWidget(label)

        # Add field form
        add_layout = QHBoxLayout()
        field_in = QLineEdit()
        field_in.setPlaceholderText("Field")
        add_layout.addWidget(field_in)

        value_in = QLineEdit()
        value_in.setPlaceholderText("Value")
        add_layout.addWidget(value_in, 1)

        def add_field():
            if field_in.text():
                try:
                    redis_manager.client.hset(key, field_in.text(), value_in.text())
                    QMessageBox.information(self, "Added", "Field added successfully")
                    self._render_hash(key)
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Error: {e}")

        add_btn = QPushButton("Add Field")
        add_btn.clicked.connect(add_field)
        add_layout.addWidget(add_btn)

        self.content_layout.addLayout(add_layout)

        # Table
        table = QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["Field", "Value"])
        table.setAlternatingRowColors(True)

        fields = redis_manager.client.hgetall(key)
        table.setRowCount(len(fields))
        for i, (field, value) in enumerate(fields.items()):
            table.setItem(i, 0, QTableWidgetItem(self._safe_str(field)))
            table.setItem(i, 1, QTableWidgetItem(self._safe_str(value)))
        table.resizeColumnsToContents()

        self.content_layout.addWidget(table, 1)

    def _add_load_more_button(self, key: str, table: QTableWidget, data_type: str, total_len: int):
        """Add a Load more button at the bottom of the table."""
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        load_more_btn = QPushButton(f"Load more (100)")
        load_more_btn.setMaximumWidth(150)

        def on_load_more():
            current_count = table.rowCount()
            if current_count >= total_len:
                load_more_btn.setVisible(False)
                return

            loaded = 0
            if data_type == "list":
                loaded = self._load_list_items(key, table, current_count, 100)
            elif data_type == "set":
                loaded = self._load_set_items(key, table, 100)
            elif data_type == "zset":
                loaded = self._load_zset_items(key, table, current_count, 100)

            if current_count + loaded >= total_len:
                load_more_btn.setVisible(False)

        load_more_btn.clicked.connect(on_load_more)
        btn_layout.addWidget(load_more_btn)
        self.content_layout.addLayout(btn_layout)

    def _render_list(self, key: str):
        total_len = redis_manager.client.llen(key)
        label = QLabel(f"Total length: {total_len}")
        label.setStyleSheet("color: gray; font-size: 11px;")
        self.content_layout.addWidget(label)

        table = QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["Index", "Value"])
        table.setAlternatingRowColors(True)
        table.setObjectName("list_table")

        # Load first 100 items
        self._load_list_items(key, table, 0, 100)

        table.resizeColumnsToContents()
        self.content_layout.addWidget(table, 1)

        # Load more button
        if total_len > 100:
            self._add_load_more_button(key, table, "list", total_len)

    def _load_list_items(self, key: str, table: QTableWidget, start: int, count: int):
        """Load list items from start index."""
        values = redis_manager.client.lrange(key, start, start + count - 1)
        current_row = table.rowCount()
        table.setRowCount(current_row + len(values))
        for i, value in enumerate(values):
            table.setItem(current_row + i, 0, QTableWidgetItem(str(start + i)))
            table.setItem(current_row + i, 1, QTableWidgetItem(self._safe_str(value)))
        table.resizeColumnsToContents()
        return len(values)

    def _render_set(self, key: str):
        total_len = redis_manager.client.scard(key)
        label = QLabel(f"Total members: {total_len}")
        label.setStyleSheet("color: gray; font-size: 11px;")
        self.content_layout.addWidget(label)

        table = QTableWidget()
        table.setColumnCount(1)
        table.setHorizontalHeaderLabels(["Member"])
        table.setAlternatingRowColors(True)
        table.setObjectName("set_table")

        # Load first 100 members
        self._load_set_items(key, table, 100)

        table.resizeColumnsToContents()
        self.content_layout.addWidget(table, 1)

        # Load more button
        if total_len > 100:
            self._add_load_more_button(key, table, "set", total_len)

    def _load_set_items(self, key: str, table: QTableWidget, count: int):
        """Load set members (sorted)."""
        # Get all members but only display up to count
        all_members = sorted(
            redis_manager.client.smembers(key), key=lambda x: self._safe_str(x)
        )
        current_row = table.rowCount()
        end_index = min(len(all_members), current_row + count)
        table.setRowCount(end_index)
        for i in range(current_row, end_index):
            table.setItem(i, 0, QTableWidgetItem(self._safe_str(all_members[i])))
        table.resizeColumnsToContents()
        return end_index - current_row

    def _render_zset(self, key: str):
        total_len = redis_manager.client.zcard(key)
        label = QLabel(f"Total members: {total_len}")
        label.setStyleSheet("color: gray; font-size: 11px;")
        self.content_layout.addWidget(label)

        table = QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["Member", "Score"])
        table.setAlternatingRowColors(True)
        table.setObjectName("zset_table")

        # Load first 100 members
        self._load_zset_items(key, table, 0, 100)

        table.resizeColumnsToContents()
        self.content_layout.addWidget(table, 1)

        # Load more button
        if total_len > 100:
            self._add_load_more_button(key, table, "zset", total_len)

    def _load_zset_items(self, key: str, table: QTableWidget, start: int, count: int):
        """Load zset members from start index."""
        members = redis_manager.client.zrange(key, start, start + count - 1, withscores=True)
        current_row = table.rowCount()
        table.setRowCount(current_row + len(members))
        for i, (member, score) in enumerate(members):
            table.setItem(current_row + i, 0, QTableWidgetItem(self._safe_str(member)))
            table.setItem(current_row + i, 1, QTableWidgetItem(str(score)))
        table.resizeColumnsToContents()
        return len(members)

    def _show_ttl_dialog(self, key: str):
        ttl, ok = QInputDialog.getInt(
            self, "Set TTL", "TTL (seconds):", -1, -1, 2147483647
        )
        if ok:
            try:
                redis_manager.set_ttl(key, ttl)
                QMessageBox.information(self, "Success", "TTL updated successfully")
                self.show_key(key)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error: {e}")

    def _show_rename_dialog(self, key: str):
        new_name, ok = QInputDialog.getText(
            self, "Rename Key", "New name:", QLineEdit.Normal, key
        )
        if ok and new_name:
            try:
                redis_manager.rename_key(key, new_name)
                QMessageBox.information(self, "Success", "Key renamed successfully")
                self.current_key = new_name
                if self.on_key_changed:
                    self.on_key_changed()
                self.show_key(new_name)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error: {e}")

    def _confirm_delete(self, key: str):
        reply = QMessageBox.question(
            self,
            "Delete Key",
            f"Delete key?\n\n{key}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            try:
                redis_manager.delete_keys(key)
                QMessageBox.information(self, "Success", f"Deleted: {key}")
                self.current_key = None
                self._show_empty()
                if self.on_key_deleted:
                    self.on_key_deleted()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error: {e}")

    @staticmethod
    def _type_color(key_type: str) -> str:
        colors = {
            "string": "#2196F3",
            "hash": "#4CAF50",
            "list": "#FF9800",
            "set": "#9C27B0",
            "zset": "#009688",
            "stream": "#F44336",
        }
        return colors.get(key_type, "#9E9E9E")

    @staticmethod
    def _try_format_json(value: str) -> str:
        try:
            return json.dumps(json.loads(value), indent=2, ensure_ascii=False)
        except (json.JSONDecodeError, TypeError):
            return value

    @staticmethod
    def _safe_str(value: object) -> str:
        if isinstance(value, bytes):
            try:
                return value.decode("utf-8")
            except UnicodeDecodeError:
                return value.hex(" ")
        return str(value)

    @staticmethod
    def _format_hex_dump(data: bytes, width: int = 16) -> str:
        lines: list[str] = []
        for offset in range(0, len(data), width):
            chunk = data[offset : offset + width]
            hex_part = " ".join(f"{b:02X}" for b in chunk)
            ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
            lines.append(f"{offset:08X}  {hex_part:<{width * 3}}  |{ascii_part}|")
        return "\n".join(lines)
