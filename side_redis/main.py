"""SideRedis - A Redis visual client built with PySide6.

Multi-threading optimized version with ThreadPoolExecutor for non-blocking Redis operations.
"""

from __future__ import annotations

import threading

from PySide6.QtCore import Signal, Slot
from PySide6.QtGui import QAction, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from side_redis.redis_client import redis_manager
from side_redis import connection_store as store
from side_redis.ui.connection import ConnectionDialog
from side_redis.ui.info_panel import InfoPanel
from side_redis.ui.key_detail import KeyDetail
from side_redis.ui.keys_browser import KeysBrowser
from side_redis.ui.terminal import Terminal


class SideRedisWindow(QMainWindow):
    """Main application window."""

    # Signal for connection status
    connected = Signal()
    disconnected = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("SideRedis")
        self.setMinimumSize(1200, 700)

        # Build UI
        self._create_menu_bar()
        self._create_toolbar()
        self._create_central_widget()
        self._create_status_bar()

        # Components
        self.conn_dialog = ConnectionDialog(self, on_connected=self._on_connected)

        # Try auto-connect after window is shown
        from PySide6.QtCore import QTimer

        QTimer.singleShot(500, self._try_auto_connect)

    def _create_menu_bar(self):
        menu = self.menuBar()

        # File menu
        file_menu = menu.addMenu("File")
        connect_action = QAction("Connect...", self)
        connect_action.triggered.connect(self._show_connection_dialog)
        file_menu.addAction(connect_action)

        disconnect_action = QAction("Disconnect", self)
        disconnect_action.triggered.connect(self._on_disconnect)
        file_menu.addAction(disconnect_action)

        file_menu.addSeparator()

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # View menu
        view_menu = menu.addMenu("View")
        self.dark_mode_action = QAction("Dark Mode", self)
        self.dark_mode_action.setCheckable(True)
        self.dark_mode_action.setChecked(True)
        self.dark_mode_action.triggered.connect(self._toggle_dark_mode)
        view_menu.addAction(self.dark_mode_action)

    def _create_toolbar(self):
        toolbar = QToolBar()
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # Connection status
        self.status_icon = QLabel("●")
        self.status_icon.setStyleSheet("color: red; font-size: 14px;")
        toolbar.addWidget(self.status_icon)

        self.status_label = QLabel("Disconnected")
        toolbar.addWidget(self.status_label)

        toolbar.addSeparator()

        # Connect button
        connect_btn = QPushButton("Connect")
        connect_btn.clicked.connect(self._show_connection_dialog)
        toolbar.addWidget(connect_btn)

        # Disconnect button
        disconnect_btn = QPushButton("Disconnect")
        disconnect_btn.clicked.connect(self._on_disconnect)
        toolbar.addWidget(disconnect_btn)

        toolbar.addSeparator()

        # New key button
        new_key_btn = QPushButton("New Key")
        new_key_btn.clicked.connect(self._show_add_key_dialog)
        toolbar.addWidget(new_key_btn)

    def _create_central_widget(self):
        central = QWidget()
        self.setCentralWidget(central)

        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Main splitter: keys browser | tab panel
        splitter = QSplitter()
        layout.addWidget(splitter)

        # Left panel: Keys browser
        self.keys_browser = KeysBrowser(self._on_key_selected)
        splitter.addWidget(self.keys_browser)

        # Right panel: Tab widget
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self.tab_widget = QTabWidget()
        right_layout.addWidget(self.tab_widget)

        # Tab 1: Key Detail
        self.key_detail = KeyDetail(
            on_key_deleted=self._on_key_deleted,
            on_key_changed=self._on_key_changed,
        )
        self.tab_widget.addTab(self.key_detail, "Key Detail")

        # Tab 2: Server Info
        self.info_panel = InfoPanel()
        self.tab_widget.addTab(self.info_panel, "Server Info")

        # Tab 3: Console
        self.terminal = Terminal()
        self.tab_widget.addTab(self.terminal, "Console")

        splitter.addWidget(right_widget)

        # Set initial splitter ratio (25% / 75%)
        splitter.setSizes([300, 900])

        # Connect tab change to refresh info panel
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

    def _create_status_bar(self):
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("Ready")

    def _try_auto_connect(self):
        """Try to auto-connect to last used or default Redis server."""
        import threading

        def try_connect():
            try:
                last = store.get_last_used()
                cfg = store.get_connection(last) if last else None

                if cfg:
                    try:
                        redis_manager.connect(**cfg)
                        from PySide6.QtCore import QTimer

                        QTimer.singleShot(0, self._on_connected)
                        return
                    except Exception:
                        pass

                # Fallback: try localhost with no auth
                try:
                    redis_manager.connect()
                    from PySide6.QtCore import QTimer

                    QTimer.singleShot(0, self._on_connected)
                except Exception:
                    pass
            except Exception:
                pass

        thread = threading.Thread(target=try_connect, daemon=True)
        thread.start()

    def _on_connected(self):
        """Handle successful connection."""
        self.status_icon.setStyleSheet("color: green; font-size: 14px;")
        self.status_label.setText(
            f"{redis_manager.host}:{redis_manager.port}/db{redis_manager.db}"
        )
        self.tab_widget.setCurrentIndex(0)
        self.keys_browser.load_initial()
        self.statusBar.showMessage(
            f"Connected to {redis_manager.host}:{redis_manager.port}"
        )

    def _show_connection_dialog(self):
        self.conn_dialog.show()

    def _on_disconnect(self):
        redis_manager.disconnect()
        self.status_icon.setStyleSheet("color: red; font-size: 14px;")
        self.status_label.setText("Disconnected")
        self.statusBar.showMessage("Disconnected")

    def _show_add_key_dialog(self):
        if not redis_manager.connected:
            QMessageBox.warning(self, "Not Connected", "Please connect to Redis first.")
            return

        from side_redis.ui.add_key_dialog import AddKeyDialog

        dialog = AddKeyDialog(self)
        if dialog.exec():
            key, value, key_type = dialog.get_values()
            self._create_key(key, value, key_type)

    def _create_key(self, key: str, value: str, key_type: str):
        """Create a new key."""
        try:
            if key_type == "string":
                redis_manager.set_key_value(key, value)
            elif key_type == "list":
                redis_manager.execute(redis_manager.client.rpush, key, value)
            elif key_type == "set":
                redis_manager.execute(redis_manager.client.sadd, key, value)
            elif key_type == "hash":
                redis_manager.execute(redis_manager.client.hset, key, "field1", value)

            self.keys_browser.load_initial()
            self.key_detail.show_key(key)
            self.statusBar.showMessage(f"Key created: {key}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create key: {e}")

    def _on_key_selected(self, key: str):
        """Handle key selection from browser."""
        self.tab_widget.setCurrentIndex(0)
        self.key_detail.show_key(key)

    def _on_key_deleted(self):
        """Handle key deletion."""
        self.keys_browser.load_initial()

    def _on_key_changed(self):
        """Handle key modification."""
        self.keys_browser.load_initial()

    def _on_tab_changed(self, index: int):
        """Handle tab switch."""
        if index == 1:  # Info tab
            self.info_panel.refresh()

    def _toggle_dark_mode(self):
        from PySide6.QtCore import Qt

        if self.dark_mode_action.isChecked():
            # Dark palette
            palette = QPalette()
            palette.setColor(QPalette.Window, Qt.GlobalColor.darkGray)
            palette.setColor(QPalette.WindowText, Qt.GlobalColor.white)
            palette.setColor(QPalette.Base, Qt.GlobalColor.darkGray)
            palette.setColor(QPalette.AlternateBase, Qt.GlobalColor.darkGray)
            palette.setColor(QPalette.ToolTipBase, Qt.GlobalColor.darkGray)
            palette.setColor(QPalette.ToolTipText, Qt.GlobalColor.white)
            palette.setColor(QPalette.Text, Qt.GlobalColor.white)
            palette.setColor(QPalette.Button, Qt.GlobalColor.darkGray)
            palette.setColor(QPalette.ButtonText, Qt.GlobalColor.white)
            palette.setColor(QPalette.BrightText, Qt.GlobalColor.red)
            palette.setColor(QPalette.Link, Qt.GlobalColor.blue)
            palette.setColor(QPalette.Highlight, Qt.GlobalColor.blue)
            palette.setColor(QPalette.HighlightedText, Qt.GlobalColor.black)
            QApplication.setPalette(palette)
        else:
            # Light palette (system default)
            QApplication.setPalette(QApplication.style().standardPalette())

    def closeEvent(self, event):
        """Cleanup on close."""
        redis_manager.disconnect()
        event.accept()


def main():
    """Run the application."""
    app = QApplication([])
    window = SideRedisWindow()
    window.show()
    app.exec()


if __name__ in {"__main__", "__mp_main__"}:
    main()
