"""Redis connection configuration dialog with saved profiles."""

from __future__ import annotations

import threading

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from side_redis.redis_client import redis_manager
from side_redis import connection_store as store


class ConnectionDialog(QDialog):
    """Connection dialog with named config management."""

    # Signals for cross-thread communication
    connect_success = Signal()
    connect_error = Signal(str)

    def __init__(self, parent=None, on_connected=None):
        super().__init__(parent)
        self.on_connected = on_connected
        self.setWindowTitle("Redis Connections")
        self.setMinimumWidth(480)

        # Connect signals
        self.connect_success.connect(self._handle_connect_success)
        self.connect_error.connect(self._handle_connect_error)

        self._build()

    def _build(self):
        layout = QVBoxLayout(self)

        title = QLabel("Redis Connections")
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)

        self.list_widget = QListWidget()
        self.list_widget.setMaximumHeight(150)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(QLabel("Saved Connections:"))
        layout.addWidget(self.list_widget)

        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator)

        form_layout = QFormLayout()

        self.name_input = QLineEdit("default")
        self.name_input.setPlaceholderText("Connection Name")
        form_layout.addRow("Name:", self.name_input)

        host_port_layout = QHBoxLayout()

        self.host_input = QLineEdit("localhost")
        self.host_input.setPlaceholderText("Host")
        host_port_layout.addWidget(self.host_input, 1)

        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(6379)
        host_port_layout.addWidget(QLabel("Port:"))
        host_port_layout.addWidget(self.port_input)

        self.db_input = QSpinBox()
        self.db_input.setRange(0, 15)
        self.db_input.setValue(0)
        host_port_layout.addWidget(QLabel("DB:"))
        host_port_layout.addWidget(self.db_input)

        form_layout.addRow("Address:", host_port_layout)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Username (optional)")
        form_layout.addRow("Username:", self.username_input)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password (optional)")
        self.password_input.setEchoMode(QLineEdit.Password)
        form_layout.addRow("Password:", self.password_input)

        layout.addLayout(form_layout)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: red; margin: 5px 0;")
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)

        button_box = QDialogButtonBox()

        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self._save_config)
        button_box.addButton(self.save_btn, QDialogButtonBox.ActionRole)

        button_box.addButton(QDialogButtonBox.Cancel)

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setDefault(True)
        self.connect_btn.clicked.connect(self._connect)
        button_box.addButton(self.connect_btn, QDialogButtonBox.ActionRole)

        layout.addWidget(button_box)

    def _refresh_list(self):
        self.list_widget.clear()
        connections = store.list_connections()
        last_used = store.get_last_used()

        if not connections:
            item = QListWidgetItem("No saved connections")
            item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
            self.list_widget.addItem(item)
            return

        for name, cfg in connections.items():
            text = f"{name} ({cfg.get('host', '?')}:{cfg.get('port', '?')}/db{cfg.get('db', 0)})"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, (name, cfg))
            if name == last_used:
                item.setText(item.text() + " ✓")
            self.list_widget.addItem(item)

    def _on_item_clicked(self, item):
        data = item.data(Qt.UserRole)
        if data:
            name, cfg = data
            self._fill_form(name, cfg)

    def _fill_form(self, name: str, cfg: dict):
        self.name_input.setText(name)
        self.host_input.setText(cfg.get("host", "localhost"))
        self.port_input.setValue(cfg.get("port", 6379))
        self.db_input.setValue(cfg.get("db", 0))
        self.username_input.setText(cfg.get("username", ""))
        self.password_input.setText(cfg.get("password", ""))

    def _save_config(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation Error", "Name is required")
            return

        store.save_connection(
            name,
            store.make_config(
                host=self.host_input.text(),
                port=self.port_input.value(),
                db=self.db_input.value(),
                username=self.username_input.text(),
                password=self.password_input.text(),
            ),
        )
        QMessageBox.information(self, "Saved", f"Saved connection: {name}")
        self._refresh_list()

    def _connect(self):
        self.error_label.setText("")

        name = self.name_input.text().strip() or "default"
        host = self.host_input.text()
        port = self.port_input.value()
        db = self.db_input.value()
        username = self.username_input.text()
        password = self.password_input.text()

        self.connect_btn.setEnabled(False)
        self.connect_btn.setText("Connecting...")

        # Start connection in background thread
        import threading

        def do_connect():
            try:
                redis_manager.connect(
                    host=host,
                    port=port,
                    db=db,
                    password=password,
                    username=username,
                )

                store.save_connection(
                    name,
                    store.make_config(
                        host=host,
                        port=port,
                        db=db,
                        username=username,
                        password=password,
                    ),
                )
                store.set_last_used(name)

                # Emit success signal
                self.connect_success.emit()

            except Exception as e:
                # Emit error signal
                self.connect_error.emit(str(e))

        thread = threading.Thread(target=do_connect, daemon=True)
        thread.start()

    def _handle_connect_success(self):
        """Handle successful connection."""
        self.connect_btn.setEnabled(True)
        self.connect_btn.setText("Connect")
        self.accept()
        if self.on_connected:
            self.on_connected()

    def _handle_connect_error(self, error_msg: str):
        """Handle connection error."""
        self.connect_btn.setEnabled(True)
        self.connect_btn.setText("Connect")
        self.error_label.setText(f"Connection failed: {error_msg}")

    def showEvent(self, event):
        super().showEvent(event)
        self.error_label.setText("")
        self._refresh_list()

        last = store.get_last_used()
        if last:
            cfg = store.get_connection(last)
            if cfg:
                self._fill_form(last, cfg)
